from datetime import datetime

from pydantic import BaseModel, Field


class TextLocation(BaseModel):
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


class TextLocationResult(BaseModel):
    review_id: str
    query: str
    locations: list[TextLocation]


class ReaderRiskLocation(BaseModel):
    status: str
    start_offset: int | None = None
    end_offset: int | None = None
    paragraph_index: int | None = None
    page_number: int | None = None
    bounding_box: list[float] | None = None
    is_ambiguous: bool = False


class ReaderKnowledgeBasis(BaseModel):
    document_id: str
    name: str
    article_number: str | None = None
    source_type: str
    status: str
    updated_at: datetime | None = None


class ReaderRisk(BaseModel):
    risk_id: str
    source_risk_id: str | None = None
    title: str
    category: str
    severity: str
    clause_text: str
    explanation: str
    recommendation: str
    suggested_revision: str | None = None
    source: str
    rule_id: str | None = None
    detection_method: str
    ai_involved: bool
    confidence: float | None = Field(default=None, ge=0, le=1)
    location: ReaderRiskLocation
    knowledge_basis: list[ReaderKnowledgeBasis] = Field(default_factory=list)
    status: str = "pending_review"
    revision: int = 1
    persisted: bool = False
    assignee_id: str | None = None
    reviewer_id: str | None = None
    review_comment: str | None = None
    revised_clause: str | None = None


class ReaderChapter(BaseModel):
    chapter_id: str
    title: str
    start_offset: int
    end_offset: int
    risk_count: int = 0
    high_risk_count: int = 0


class ReaderWorkspaceSummary(BaseModel):
    review_id: str
    contract_id: str | None = None
    contract_version_id: str | None = None
    contract_name: str
    contract_type: str
    contract_version: int | None = None
    status: str
    reviewed_at: datetime
    operator_name: str | None = None
    overall_risk_level: str | None = None
    risk_score: float | None = None
    risk_count: int
    report_available: bool
    source_is_pdf: bool


class ReaderWorkspace(BaseModel):
    summary: ReaderWorkspaceSummary
    contract_text: str
    risks: list[ReaderRisk] = Field(default_factory=list)
    chapters: list[ReaderChapter] = Field(default_factory=list)
