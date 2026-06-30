from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str = "1.0.0"


class IngestResponse(BaseModel):
    claims_loaded: Optional[int] = None
    unique_claims: Optional[int] = None
    ncci_pairs_loaded: Optional[int] = None 
    message: str


class AnalysisResponse(BaseModel):
    timeline: Dict[str, Any]
    baselines_computed: int
    unbundling_flags: int
    upcoding_flags: int
    total_flags: int
    total_financial_risk: float


class FlagResponse(BaseModel):
    id: int
    flag_type: str
    clm_id: str
    desynpuf_id: str
    service_date: date
    financial_risk: float
    confidence_score: float
    rule_id: Optional[str]
    rule_description: Optional[str]
    violated_codes: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    total_flags: int
    open_flags: int
    unbundling_count: int
    upcoding_count: int
    total_financial_risk: float
    avg_confidence: float
    patient_days_analyzed: Optional[int] = None


class PipelineRunResponse(BaseModel):
    ingest: Dict[str, Any]
    analysis: AnalysisResponse
    message: str
