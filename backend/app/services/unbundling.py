"""NCCI-based unbundling detection."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import NCCIPair
from app.services.timeline import DailyClaimGroup


@dataclass
class UnbundlingViolation:
    desynpuf_id: str
    service_date: str
    clm_ids: list[str]
    code_a: str
    code_b: str
    modifier_indicator: str | None
    financial_risk: float
    confidence_score: float
    rule_id: str
    rule_description: str
    evidence: dict


def _build_ncci_lookup(db: Session) -> dict[frozenset[str], list[NCCIPair]]:
    lookup: dict[frozenset[str], list[NCCIPair]] = {}
    for pair in db.query(NCCIPair).all():
        key = frozenset({pair.procedure_code_a, pair.procedure_code_b})
        lookup.setdefault(key, []).append(pair)
    return lookup


def _modifier_allows_billing(modifier: str | None) -> bool:
    """Modifier 1 = not allowed; 0/blank = allowed with modifier; 9 = not applicable."""
    if modifier is None or modifier == "":
        return False
    return modifier in {"0", "1"}


def detect_unbundling(db: Session, groups: list[DailyClaimGroup]) -> list[UnbundlingViolation]:
    lookup = _build_ncci_lookup(db)
    violations: list[UnbundlingViolation] = []

    for group in groups:
        codes = sorted(group.hcpcs_codes)
        if len(codes) < 2:
            continue

        checked: set[frozenset[str]] = set()
        for i, code_a in enumerate(codes):
            for code_b in codes[i + 1 :]:
                key = frozenset({code_a, code_b})
                if key in checked:
                    continue
                checked.add(key)

                pairs = lookup.get(key)
                if not pairs:
                    continue

                pair = pairs[0]
                col1, col2 = pair.procedure_code_a, pair.procedure_code_b
                denied_code = col2 if col1 in group.hcpcs_codes else col1
                allowed_code = col1 if denied_code == col2 else col2

                denied_lines = [ln for ln in group.lines if ln.hcpcs_cd == denied_code]
                financial_risk = sum(ln.clm_pmt_amt or 0 for ln in denied_lines)

                modifier_blocks = _modifier_allows_billing(pair.modifier_indicator)
                confidence = 0.95 if pair.modifier_indicator == "1" else 0.82
                if modifier_blocks:
                    confidence = min(confidence + 0.03, 0.99)

                violations.append(
                    UnbundlingViolation(
                        desynpuf_id=group.desynpuf_id,
                        service_date=group.service_date.isoformat(),
                        clm_ids=sorted(group.claim_ids),
                        code_a=allowed_code,
                        code_b=denied_code,
                        modifier_indicator=pair.modifier_indicator,
                        financial_risk=round(financial_risk, 2),
                        confidence_score=round(confidence, 3),
                        rule_id=f"NCCI-PTP-{allowed_code}-{denied_code}",
                        rule_description=(
                            f"NCCI PTP edit: {denied_code} is bundled into {allowed_code} "
                            f"and should not be billed separately on the same date of service."
                        ),
                        evidence={
                            "patient_id": group.desynpuf_id,
                            "service_date": group.service_date.isoformat(),
                            "billed_codes": sorted(group.hcpcs_codes),
                            "column_one": allowed_code,
                            "column_two": denied_code,
                            "modifier_indicator": pair.modifier_indicator,
                            "claim_ids": sorted(group.claim_ids),
                            "total_day_payment": round(group.total_payment, 2),
                        },
                    )
                )

    return violations
