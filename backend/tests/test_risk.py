from datetime import date

from app.models import RiskLevel, Sanction, SanctionsResult
from app.risk import assess
from app.sources import parse_brasilapi
from tests.fixtures import CLOSED, COMPANIES, ESTABLISHED, NEW_TINY

TODAY = date(2026, 9, 29)
CLEAN = SanctionsResult(checked=True)


def codes(assessment) -> set[str]:
    return {s.code for s in assessment.signals}


def test_established_clean_company_is_low_risk() -> None:
    result = assess(parse_brasilapi(COMPANIES[ESTABLISHED]), CLEAN, TODAY)
    assert result.level == RiskLevel.LOW
    assert result.score == 0
    assert result.complete


def test_closed_company_is_critical() -> None:
    result = assess(parse_brasilapi(COMPANIES[CLOSED]), CLEAN, TODAY)
    assert result.level == RiskLevel.CRITICAL
    assert "STATUS_NOT_ACTIVE" in codes(result)


def test_new_company_with_symbolic_capital_and_no_partners() -> None:
    result = assess(parse_brasilapi(COMPANIES[NEW_TINY]), CLEAN, TODAY)
    assert codes(result) == {"VERY_NEW_COMPANY", "LOW_SHARE_CAPITAL", "NO_PARTNERS_LISTED"}
    assert result.score == 25
    assert result.level == RiskLevel.MEDIUM


def test_active_sanction_is_critical_and_past_sanction_is_medium() -> None:
    company = parse_brasilapi(COMPANIES[ESTABLISHED])

    active = SanctionsResult(checked=True, sanctions=[Sanction(registry="CEIS", end=None)])
    assert assess(company, active, TODAY).level == RiskLevel.CRITICAL

    past = SanctionsResult(
        checked=True, sanctions=[Sanction(registry="CNEP", end=date(2020, 1, 1))]
    )
    result = assess(company, past, TODAY)
    assert codes(result) == {"PAST_SANCTIONS"}
    assert result.level == RiskLevel.MEDIUM


def test_unchecked_sanctions_marks_assessment_incomplete_without_points() -> None:
    unchecked = SanctionsResult(checked=False, note="sem chave")
    result = assess(parse_brasilapi(COMPANIES[ESTABLISHED]), unchecked, TODAY)
    assert not result.complete
    assert result.score == 0
    assert "SANCTIONS_NOT_CHECKED" in codes(result)


def test_every_signal_cites_a_source() -> None:
    result = assess(parse_brasilapi(COMPANIES[CLOSED]), SanctionsResult(checked=False), TODAY)
    assert all(s.source for s in result.signals)


def test_share_capital_is_shown_in_brl() -> None:
    result = assess(parse_brasilapi(COMPANIES[NEW_TINY]), CLEAN, TODAY)
    message = next(s.message for s in result.signals if s.code == "LOW_SHARE_CAPITAL")
    assert "BRL 100.00" in message
