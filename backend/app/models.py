"""Domain models. Facts come from public sources; the LLM only writes the narrative."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class Partner(BaseModel):
    name: str
    role: str | None = None
    document: str | None = None  # masked CPF or full CNPJ, as published by Receita
    since: date | None = None

    @property
    def is_company(self) -> bool:
        return bool(self.document) and len(self.document) == 14 and self.document.isdigit()


class CompanyProfile(BaseModel):
    cnpj: str
    legal_name: str
    trade_name: str | None = None
    status: str  # as published by Receita: "ATIVA", "BAIXADA", "INAPTA", "SUSPENSA", "NULA"
    status_reason: str | None = None
    status_date: date | None = None
    special_situation: str | None = None
    opened_on: date | None = None
    legal_nature: str | None = None
    size: str | None = None
    share_capital: float | None = None
    main_activity_code: int | None = None
    main_activity: str | None = None
    secondary_activities: list[str] = Field(default_factory=list)
    city: str | None = None
    state: str | None = None
    partners: list[Partner] = Field(default_factory=list)


class Sanction(BaseModel):
    registry: str  # "CEIS" or "CNEP"
    sanction_type: str | None = None
    authority: str | None = None
    start: date | None = None
    end: date | None = None
    process_number: str | None = None
    link: str | None = None

    def is_active(self, today: date) -> bool:
        return self.end is None or self.end >= today


class SanctionsResult(BaseModel):
    checked: bool
    sanctions: list[Sanction] = Field(default_factory=list)
    note: str | None = None


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskSignal(BaseModel):
    code: str
    severity: Severity
    points: int
    message: str
    source: str


class RiskAssessment(BaseModel):
    score: int
    level: RiskLevel
    signals: list[RiskSignal]
    complete: bool  # False when a source could not be checked


class ActivityFit(StrEnum):
    COMPATIBLE = "compatible"
    PARTIAL = "partial"
    INCOMPATIBLE = "incompatible"
    NOT_EVALUATED = "not_evaluated"


class Narrative(BaseModel):
    """The only part of the report written by the model."""

    summary: str
    activity_fit: ActivityFit
    activity_fit_reason: str
    attention_points: list[str]
    recommendations: list[str]


class SourceRef(BaseModel):
    name: str
    url: str
    consulted_at: str


class Report(BaseModel):
    company: CompanyProfile
    sanctions: SanctionsResult
    risk: RiskAssessment
    narrative: Narrative
    related_companies: list[CompanyProfile] = Field(default_factory=list)
    sources: list[SourceRef]
    model: str
    language: str = "en"
