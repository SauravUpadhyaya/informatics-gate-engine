import json
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text
from app.database import Base # Or your active database Base configuration

class ComplianceFlag(Base):
    __tablename__ = "compliance_flags"

    id = Column(Integer, primary_key=True, index=True)
    flag_type = Column(String(50), nullable=False) # "unbundling" or "upcoding"
    clm_id = Column(String(100), index=True, nullable=False)
    desynpuf_id = Column(String(100), index=True, nullable=False)
    service_date = Column(Date, nullable=False)
    financial_risk = Column(Float, nullable=False)
    confidence_score = Column(Float, default=1.0)
    rule_id = Column(String(100), nullable=True)
    rule_description = Column(Text, nullable=True)
    
    # Store violated codes as a comma-separated text string or JSON
    _violated_codes_str = Column("violated_codes", Text, default="[]")
    _evidence_str = Column("evidence", Text, default="{}")

    status = Column(String(50), default="open")
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def violated_codes(self):
        try:
            return json.loads(self._violated_codes_str)
        except:
            return []

    @violated_codes.setter
    def violated_codes(self, val):
        self._violated_codes_str = json.dumps(val)

    @property
    def evidence(self):
        try:
            return json.loads(self._evidence_str)
        except:
            return {}

    @evidence.setter
    def evidence(self, val):
        self._evidence_str = json.dumps(val)
