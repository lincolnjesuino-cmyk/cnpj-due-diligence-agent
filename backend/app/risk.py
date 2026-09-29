"""Deterministic risk scoring.

The score is computed in code, never by the model: the same inputs always produce the
same level, every point is traceable to a public source, and it is unit-tested.
"""

from datetime import date

from app.models import (
    CompanyProfile,
    RiskAssessment,
    RiskLevel,
    RiskSignal,
    SanctionsResult,
    Severity,
)

RECEITA = "Receita Federal (company registry)"
TRANSPARENCIA = "Portal da Transparência (CEIS/CNEP debarment lists)"

# Legal natures where an empty shareholder list (QSA) is expected: sole proprietors, MEIs.
_NO_QSA_EXPECTED = ("empresário (individual)", "empresario (individual)", "microempreendedor")


def _level(score: int) -> RiskLevel:
    if score >= 50:
        return RiskLevel.CRITICAL
    if score >= 30:
        return RiskLevel.HIGH
    if score >= 10:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _years_between(start: date, end: date) -> float:
    return (end - start).days / 365.25


def assess(
    company: CompanyProfile,
    sanctions: SanctionsResult,
    today: date | None = None,
) -> RiskAssessment:
    today = today or date.today()
    signals: list[RiskSignal] = []

    if company.status != "ATIVA":
        reason = f" ({company.status_reason})" if company.status_reason else ""
        signals.append(
            RiskSignal(
                code="STATUS_NOT_ACTIVE",
                severity=Severity.CRITICAL,
                points=50,
                message=f"Registration status is {company.status}{reason}, not active.",
                source=RECEITA,
            )
        )

    if company.special_situation:
        signals.append(
            RiskSignal(
                code="SPECIAL_SITUATION",
                severity=Severity.HIGH,
                points=25,
                message=f"Special situation on record: {company.special_situation}.",
                source=RECEITA,
            )
        )

    active = [s for s in sanctions.sanctions if s.is_active(today)]
    expired = [s for s in sanctions.sanctions if not s.is_active(today)]
    for s in active:
        signals.append(
            RiskSignal(
                code=f"ACTIVE_SANCTION_{s.registry}",
                severity=Severity.CRITICAL,
                points=50,
                message=f"Active sanction on {s.registry}: {s.sanction_type or 'type not stated'}"
                f" — {s.authority or 'authority not stated'}.",
                source=TRANSPARENCIA,
            )
        )
    if expired:
        signals.append(
            RiskSignal(
                code="PAST_SANCTIONS",
                severity=Severity.MEDIUM,
                points=10,
                message=f"{len(expired)} expired sanction(s) in the CEIS/CNEP history.",
                source=TRANSPARENCIA,
            )
        )
    if not sanctions.checked:
        signals.append(
            RiskSignal(
                code="SANCTIONS_NOT_CHECKED",
                severity=Severity.INFO,
                points=0,
                message=sanctions.note or "Debarment lists could not be checked.",
                source=TRANSPARENCIA,
            )
        )

    if company.opened_on:
        age = _years_between(company.opened_on, today)
        if age < 1:
            signals.append(
                RiskSignal(
                    code="VERY_NEW_COMPANY",
                    severity=Severity.MEDIUM,
                    points=15,
                    message=f"Company is less than 1 year old (opened {company.opened_on}).",
                    source=RECEITA,
                )
            )
        elif age < 2:
            signals.append(
                RiskSignal(
                    code="NEW_COMPANY",
                    severity=Severity.LOW,
                    points=5,
                    message=f"Company is less than 2 years old (opened {company.opened_on}).",
                    source=RECEITA,
                )
            )

    if company.share_capital is not None and company.share_capital < 1_000:
        signals.append(
            RiskSignal(
                code="LOW_SHARE_CAPITAL",
                severity=Severity.LOW,
                points=5,
                message=f"Declared share capital is very low (BRL {company.share_capital:,.2f}).",
                source=RECEITA,
            )
        )

    nature = (company.legal_nature or "").lower()
    if not company.partners and not any(n in nature for n in _NO_QSA_EXPECTED):
        signals.append(
            RiskSignal(
                code="NO_PARTNERS_LISTED",
                severity=Severity.LOW,
                points=5,
                message="No shareholders listed, although this legal form normally has them.",
                source=RECEITA,
            )
        )

    score = sum(s.points for s in signals)
    return RiskAssessment(
        score=score,
        level=_level(score),
        signals=signals,
        complete=sanctions.checked,
    )
