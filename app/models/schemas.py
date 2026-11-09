from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ContactModel(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None


class CompanyModel(BaseModel):
    id: str
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    number_of_employees: Optional[str] = None
    annual_revenue: Optional[str] = None


class EngagementModel(BaseModel):
    id: str
    type: str  # NOTE, CALL, MEETING, EMAIL
    body: str
    created_at: Optional[str] = None
    author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DealModel(BaseModel):
    id: str
    name: str
    amount: Optional[float] = None
    stage: Optional[str] = None
    pipeline: Optional[str] = None
    close_date: Optional[str] = None
    owner_id: Optional[str] = None
    company: Optional[CompanyModel] = None
    contacts: List[ContactModel] = Field(default_factory=list)
    engagements: List[EngagementModel] = Field(default_factory=list)
    raw_properties: Dict[str, Any] = Field(default_factory=dict)


class TextChunk(BaseModel):
    id: str
    deal_id: str
    source_type: str  # NOTE, CALL, EMAIL, MEETING, CRM_FIELD, CRM_RECORD, CALL_TRANSCRIPT
    source_id: str
    content: str
    speaker_or_author: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerifiedClaim(BaseModel):
    claim_text: str
    source_citation: Optional[str] = None
    status: str = "GROUNDED"  # GROUNDED, UNSUPPORTED, CONTRADICTED
    confidence_score: float = 1.0


class MeddicSection(BaseModel):
    title: str
    key_findings: List[str]
    claims: List[VerifiedClaim] = Field(default_factory=list)
    strategy_recommendation: Optional[str] = None


class BattlecardItem(BaseModel):
    them: str
    us: str
    source: str = "CRM Notes"


class CompetitorWatchItem(BaseModel):
    strength: str
    action: str
    source: str = "CRM Signal"


class PlaybookOutput(BaseModel):
    deal_id: str
    deal_name: str
    generated_at: str
    methodology: str = "MEDDIC"
    confidence_score: float = 4.5
    deal_summary: str

    # MEDDIC Core Sections
    metrics: MeddicSection
    economic_buyer: MeddicSection
    decision_criteria: MeddicSection
    decision_process: MeddicSection
    identify_pain: MeddicSection
    champion: MeddicSection

    # Strategy & Competitive
    competitive_landscape: MeddicSection
    battlecards: List[BattlecardItem] = Field(default_factory=list)
    watch_items: List[CompetitorWatchItem] = Field(default_factory=list)
    recommended_talk_tracks: List[str] = Field(default_factory=list)
    unverified_alerts: List[str] = Field(default_factory=list)
