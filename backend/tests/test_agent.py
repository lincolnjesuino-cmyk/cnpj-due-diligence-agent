import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent import AgentError, DueDiligenceAgent
from app.models import CompanyProfile, RiskLevel, SanctionsResult, SourceRef
from app.sources import CompanyNotFoundError, parse_brasilapi
from tests.fixtures import CLOSED, COMPANIES, ESTABLISHED, HOLDING

NARRATIVE = {
    "summary": "Active since 2010, no federal sanctions.",
    "activity_fit": "compatible",
    "activity_fit_reason": "Primary CNAE is building construction.",
    "attention_points": [],
    "recommendations": ["Request a federal tax clearance certificate."],
}


def tool_use(id_: str, name: str, cnpj: str) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id_, name=name, input={"cnpj": cnpj})


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def response(stop_reason: str, *blocks: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


class ScriptedClaude:
    """Stands in for AsyncAnthropic: returns scripted turns and records requests."""

    def __init__(self, turns: list[SimpleNamespace]) -> None:
        self._turns = iter(turns)
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> SimpleNamespace:
        # Snapshot: the agent keeps appending to the same list after this call.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return next(self._turns)


class FakeData:
    def __init__(self) -> None:
        self.consulted: list[SourceRef] = []
        self.calls: list[tuple[str, str]] = []

    async def company(self, cnpj: str) -> CompanyProfile:
        self.calls.append(("company", cnpj))
        if cnpj not in COMPANIES:
            raise CompanyNotFoundError(f"CNPJ {cnpj} not found")
        self.consulted.append(SourceRef(name="Receita", url=f"fake://{cnpj}", consulted_at="t"))
        return parse_brasilapi(COMPANIES[cnpj])

    async def sanctions(self, cnpj: str) -> SanctionsResult:
        self.calls.append(("sanctions", cnpj))
        return SanctionsResult(checked=True)


async def run(turns: list[SimpleNamespace], cnpj: str = ESTABLISHED):
    claude, data, events = ScriptedClaude(turns), FakeData(), []

    async def emit(event: dict[str, Any]) -> None:
        events.append(event)

    agent = DueDiligenceAgent(claude, data, model="claude-opus-5-5", max_turns=5)  # type: ignore[arg-type]
    report = await agent.run(cnpj, "Hire a contractor to build a warehouse", emit)
    return report, claude, data, events


async def test_full_investigation_including_partner_company() -> None:
    report, claude, data, events = await run(
        [
            response(
                "tool_use",
                tool_use("t1", "lookup_company", ESTABLISHED),
                tool_use("t2", "check_sanctions", ESTABLISHED),
            ),
            response(
                "tool_use",
                tool_use("t3", "lookup_company", HOLDING),
                tool_use("t4", "assess_risk", ESTABLISHED),
            ),
            response("end_turn", text(json.dumps(NARRATIVE))),
        ]
    )

    assert report.company.legal_name == "CONSTRUTORA EXEMPLO LTDA"
    assert report.risk.level == RiskLevel.LOW
    assert [c.cnpj for c in report.related_companies] == [HOLDING]
    assert report.narrative.recommendations == ["Request a federal tax clearance certificate."]

    # Parallel tool calls come back as ONE user message with every result.
    second_request = claude.requests[1]["messages"]
    results = second_request[-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert not any(r["is_error"] for r in results)

    # The purpose reaches the model; cached facts are not fetched twice.
    assert "warehouse" in claude.requests[0]["messages"][0]["content"]
    assert data.calls.count(("company", ESTABLISHED)) == 1

    assert [e["type"] for e in events].count("tool_call") == 4
    assert events[-1]["type"] == "report"


async def test_report_facts_come_from_code_even_if_model_skips_tools() -> None:
    report, _, data, _ = await run([response("end_turn", text(json.dumps(NARRATIVE)))], CLOSED)

    # The model claimed nothing about status; the code still fetched and scored it.
    assert report.company.status == "BAIXADA"
    assert report.risk.level == RiskLevel.CRITICAL
    assert ("company", CLOSED) in data.calls


async def test_tool_errors_are_returned_to_the_model_not_raised() -> None:
    _, claude, _, events = await run(
        [
            response("tool_use", tool_use("t1", "lookup_company", "00000000000000")),
            response("end_turn", text(json.dumps(NARRATIVE))),
        ]
    )
    result = claude.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True
    assert "Invalid CNPJ" in result["content"]
    assert events[1] == {
        "type": "tool_result",
        "tool": "lookup_company",
        "input": {"cnpj": "00000000000000"},
        "ok": False,
    }


async def test_request_shape() -> None:
    _, claude, _, _ = await run([response("end_turn", text(json.dumps(NARRATIVE)))])
    request = claude.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert all(t["strict"] for t in request["tools"])
    assert "tool_choice" not in request  # forced tool choice is rejected on this model


@pytest.mark.parametrize(
    ("turn", "message"),
    [
        (response("end_turn", text("not json")), "expected format"),
        (response("refusal"), "refused"),
        (response("max_tokens", text("{")), "truncated"),
    ],
)
async def test_bad_final_turns_raise_agent_error(turn: SimpleNamespace, message: str) -> None:
    with pytest.raises(AgentError, match=message):
        await run([turn])


async def test_turn_limit() -> None:
    loop = [
        response("tool_use", tool_use(f"t{i}", "lookup_company", ESTABLISHED)) for i in range(5)
    ]
    with pytest.raises(AgentError, match="limit"):
        await run(loop)


async def test_language_parameter_reaches_the_prompt() -> None:
    claude, events = ScriptedClaude([response("end_turn", text(json.dumps(NARRATIVE)))]), []

    async def emit(event: dict[str, Any]) -> None:
        events.append(event)

    agent = DueDiligenceAgent(claude, FakeData(), model="claude-opus-5-5")  # type: ignore[arg-type]
    report = await agent.run(ESTABLISHED, None, emit, language="pt")

    assert "Brazilian Portuguese" in claude.requests[0]["system"]
    assert report.language == "pt"
    assert "not provided" in claude.requests[0]["messages"][0]["content"]
