"""Build patient-day timelines from claim lines."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.models import ClaimLine


@dataclass
class DailyClaimGroup:
    desynpuf_id: str
    service_date: date
    claim_ids: set[str] = field(default_factory=set)
    hcpcs_codes: set[str] = field(default_factory=set)
    lines: list[ClaimLine] = field(default_factory=list)
    total_payment: float = 0.0
    primary_diagnoses: set[str] = field(default_factory=set)
    drg_codes: set[str] = field(default_factory=set)

    def add_line(self, line: ClaimLine) -> None:
        self.lines.append(line)
        self.claim_ids.add(line.clm_id)
        if line.hcpcs_cd:
            self.hcpcs_codes.add(line.hcpcs_cd)
        self.total_payment += line.clm_pmt_amt or 0.0
        if line.primary_dx:
            self.primary_diagnoses.add(line.primary_dx)
        if line.drg_cd:
            self.drg_codes.add(line.drg_cd)


from app.models import ClaimLine
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

def build_patient_timelines(db: Session):
    """
    Groups flat database claim rows into structured patient-day windows.
    """
    # 🛠️ HARDENED: Query every single claim row without any historical date caps or status filters
    lines = db.query(ClaimLine).all()
    
    # Print the exact count to your Uvicorn logs terminal to track database status
    print(f"\n🚀 TIMELINE LOG: Total rows physically found in DB table: {len(lines)}")
    
    if not lines:
        return {}
        
    groups = {}
    for line in lines:
        # Guarantee we convert the patient ID key safely to a string token
        pid = str(line.desynpuf_id).strip()
        
        # 🛠️ CRITICAL FIX: Handle both standard datetime.date objects and string types gracefully
        if hasattr(line.service_date, "strftime"):
            s_date = line.service_date.strftime("%Y-%m-%d")
        else:
            s_date = str(line.service_date).strip()
            
        if not pid or not s_date or pid == "None" or s_date == "None":
            continue
            
        key = (pid, s_date)
        if key not in groups:
            groups[key] = []
        groups[key].append(line)
        
    print(f"🚀 TIMELINE LOG: Successfully built {len(groups)} aggregated patient-day windows.\n")
    return groups



def timeline_summary(groups: list[DailyClaimGroup]) -> dict:
    multi_code_days = sum(1 for g in groups if len(g.hcpcs_codes) > 1)
    return {
        "patient_days": len(groups),
        "unique_patients": len({g.desynpuf_id for g in groups}),
        "multi_procedure_days": multi_code_days,
        "avg_codes_per_day": round(
            sum(len(g.hcpcs_codes) for g in groups) / max(len(groups), 1), 2
        ),
    }
