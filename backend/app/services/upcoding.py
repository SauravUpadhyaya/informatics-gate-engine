"""Statistical upcoding detection based on diagnosis complexity baselines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ClaimLine, DiagnosisBaseline
from app.services.timeline import DailyClaimGroup

# RVU-style complexity weights (relative value units proxy for demo)
PROCEDURE_COMPLEXITY = {
    "99211": 1, "99212": 2, "99213": 3, "99214": 5, "99215": 7,
    "99281": 2, "99282": 4, "99283": 6, "99284": 9, "99285": 12,
    "93000": 3, "93005": 4, "93010": 5,
    "71020": 4, "71046": 6, "71250": 10, "71260": 14,
    "36415": 2, "80053": 3, "85025": 3, "81001": 2,
    "29881": 18, "27447": 22, "93458": 28, "92928": 25,
    "45378": 12, "43239": 15, "47562": 20,
    "G0438": 4, "G0439": 4,
}

DIAGNOSIS_LABELS = {
    "460": "Acute respiratory infection",
    "461": "Acute sinusitis",
    "462": "Acute pharyngitis",
    "465": "Acute URI",
    "486": "Pneumonia",
    "491": "COPD",
    "250": "Diabetes mellitus",
    "401": "Hypertension",
    "414": "Coronary artery disease",
    "428": "Heart failure",
    "599": "UTI",
    "789": "Abdominal pain",
    "V58": "Encounter for other prophylactic care",
}


def _dx_group(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip().upper()
    if code.startswith("V"):
        return code[:3]
    digits = "".join(c for c in code if c.isdigit())
    if len(digits) >= 3:
        return digits[:3]
    return code[:3]


def _dx_label(group: str) -> str:
    return DIAGNOSIS_LABELS.get(group, f"Diagnosis group {group}")


def _procedure_complexity(code: str | None, payment: float) -> float:
    if not code:
        return max(payment / 100.0, 1.0)
    base = PROCEDURE_COMPLEXITY.get(code.upper())
    if base is not None:
        return float(base)
    return max(payment / 150.0, 2.0)


@dataclass
class UpcodingViolation:
    desynpuf_id: str
    service_date: str
    clm_id: str
    hcpcs_cd: str
    diagnosis_group: str
    diagnosis_label: str
    observed_complexity: float
    expected_complexity: float
    z_score: float
    financial_risk: float
    confidence_score: float
    rule_id: str
    rule_description: str
    evidence: dict


def compute_baselines(db: Session) -> list[DiagnosisBaseline]:
    lines = db.query(ClaimLine).all()
    rows = []
    for line in lines:
        group = _dx_group(line.primary_dx)
        if not group or not line.hcpcs_cd:
            continue
        complexity = _procedure_complexity(line.hcpcs_cd, line.clm_pmt_amt or 0)
        rows.append(
            {
                "diagnosis_group": group,
                "payment": line.clm_pmt_amt or 0,
                "complexity": complexity,
            }
        )

    if not rows:
        return []

    df = pd.DataFrame(rows)
    db.query(DiagnosisBaseline).delete()

    baselines: list[DiagnosisBaseline] = []
    for group, grp in df.groupby("diagnosis_group"):
        if len(grp) < settings.upcoding_min_group_size:
            continue
        baseline = DiagnosisBaseline(
            diagnosis_group=group,
            diagnosis_label=_dx_label(group),
            claim_count=int(len(grp)),
            avg_payment=float(grp["payment"].mean()),
            std_payment=float(grp["payment"].std(ddof=0) or 1.0),
            avg_complexity=float(grp["complexity"].mean()),
            std_complexity=float(grp["complexity"].std(ddof=0) or 1.0),
            p75_complexity=float(np.percentile(grp["complexity"], 75)),
            p90_complexity=float(np.percentile(grp["complexity"], 90)),
            updated_at=datetime.utcnow(),
        )
        baselines.append(baseline)

    db.bulk_save_objects(baselines)
    db.commit()
    return baselines


def detect_upcoding(
    db: Session,
    groups: list[DailyClaimGroup],
    baselines: list[DiagnosisBaseline] | None = None,
) -> list[UpcodingViolation]:
    if baselines is None:
        baselines = db.query(DiagnosisBaseline).all()

    baseline_map = {b.diagnosis_group: b for b in baselines}
    violations: list[UpcodingViolation] = []

    for group in groups:
        for line in group.lines:
            group_code = _dx_group(line.primary_dx)
            if not group_code or not line.hcpcs_cd:
                continue

            baseline = baseline_map.get(group_code)
            if not baseline:
                continue

            observed = _procedure_complexity(line.hcpcs_cd, line.clm_pmt_amt or 0)
            z_score = (observed - baseline.avg_complexity) / max(baseline.std_complexity, 0.5)

            exceeds_threshold = z_score >= settings.upcoding_zscore_threshold
            exceeds_p90 = observed >= baseline.p90_complexity + 2

            if not (exceeds_threshold or exceeds_p90):
                continue

            payment = line.clm_pmt_amt or 0
            expected_payment = baseline.avg_payment
            financial_risk = max(payment - expected_payment, payment * 0.35)

            confidence = min(0.55 + (z_score / 10), 0.97)
            if observed >= baseline.p90_complexity + 5:
                confidence = min(confidence + 0.08, 0.98)

            violations.append(
                UpcodingViolation(
                    desynpuf_id=line.desynpuf_id,
                    service_date=line.service_date.isoformat(),
                    clm_id=line.clm_id,
                    hcpcs_cd=line.hcpcs_cd,
                    diagnosis_group=group_code,
                    diagnosis_label=baseline.diagnosis_label,
                    observed_complexity=round(observed, 2),
                    expected_complexity=round(baseline.avg_complexity, 2),
                    z_score=round(z_score, 2),
                    financial_risk=round(financial_risk, 2),
                    confidence_score=round(confidence, 3),
                    rule_id=f"UPCODE-{group_code}-{line.hcpcs_cd}",
                    rule_description=(
                        f"Procedure {line.hcpcs_cd} complexity ({observed:.1f}) exceeds "
                        f"baseline for {baseline.diagnosis_label} "
                        f"(avg {baseline.avg_complexity:.1f}, z={z_score:.1f})."
                    ),
                    evidence={
                        "patient_id": line.desynpuf_id,
                        "claim_id": line.clm_id,
                        "service_date": line.service_date.isoformat(),
                        "primary_diagnosis": line.primary_dx,
                        "diagnosis_group": group_code,
                        "procedure_code": line.hcpcs_cd,
                        "observed_complexity": observed,
                        "baseline_avg_complexity": baseline.avg_complexity,
                        "baseline_p90_complexity": baseline.p90_complexity,
                        "z_score": z_score,
                        "claim_payment": payment,
                        "baseline_avg_payment": baseline.avg_payment,
                    },
                )
            )

    return violations
