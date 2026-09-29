"""Behavioral evals for the due diligence agent.

Runs the real agent (real Claude API calls) against fixed, synthetic public-data fixtures,
so every run sees identical facts and any change in the score comes from the model or the
prompt. Graders are code-based: deterministic and free to re-run.

Usage (from backend/):  python -m evals.run_evals
Cost: 5 cases x 2-4 model turns each. Requires ANTHROPIC_API_KEY.
"""

import asyncio
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

from app.agent import DueDiligenceAgent
from app.config import get_settings
from app.models import CompanyProfile, Report, Sanction, SanctionsResult, SourceRef
from app.sources import CompanyNotFoundError, parse_brasilapi
from tests.fixtures import CLOSED, COMPANIES, ESTABLISHED, HOLDING, NEW_TINY

RESULTS_DIR = Path(__file__).parent / "results"
PASS_THRESHOLD = 0.9


class FixtureData:
    """Offline stand-in for PublicDataClient."""

    def __init__(self, sanctioned: set[str] | None = None) -> None:
        self.sanctioned = sanctioned or set()
        self.consulted: list[SourceRef] = []

    async def company(self, cnpj: str) -> CompanyProfile:
        if cnpj not in COMPANIES:
            raise CompanyNotFoundError(f"CNPJ {cnpj} not found in the Receita Federal registry.")
        self.consulted.append(SourceRef(name="fixture", url=f"fixture://{cnpj}", consulted_at="-"))
        return parse_brasilapi(COMPANIES[cnpj])

    async def sanctions(self, cnpj: str) -> SanctionsResult:
        if cnpj not in self.sanctioned:
            return SanctionsResult(checked=True)
        return SanctionsResult(
            checked=True,
            sanctions=[
                Sanction(
                    registry="CEIS",
                    sanction_type="Impedimento de licitar e contratar",
                    authority="PREFEITURA MUNICIPAL DE EXEMPLO",
                )
            ],
        )


Events = list[dict[str, Any]]
Check = tuple[str, Callable[[Report, Events], bool]]


@dataclass
class Case:
    name: str
    cnpj: str
    purpose: str | None
    checks: list[Check]
    sanctioned: set[str] = field(default_factory=set)


def called(events: Events, tool: str, cnpj: str) -> bool:
    return any(
        e["type"] == "tool_call"
        and e["tool"] == tool
        and "".join(c for c in e["input"].get("cnpj", "") if c.isdigit()) == cnpj
        for e in events
    )


def prose(report: Report) -> str:
    n = report.narrative
    return " ".join([n.summary, n.activity_fit_reason, *n.attention_points]).lower()


def mentions(report: Report, *words: str) -> bool:
    text = prose(report) + " " + " ".join(report.narrative.recommendations).lower()
    return any(w in text for w in words)


CASES = [
    Case(
        "healthy_contractor_with_corporate_shareholder",
        ESTABLISHED,
        "Hire a contractor to build a warehouse",
        [
            ("risk level LOW", lambda r, e: r.risk.level == "LOW"),
            ("activity compatible", lambda r, e: r.narrative.activity_fit == "compatible"),
            (
                "investigated the shareholder company",
                lambda r, e: called(e, "lookup_company", HOLDING),
            ),
            ("checked target sanctions", lambda r, e: called(e, "check_sanctions", ESTABLISHED)),
            ("called assess_risk", lambda r, e: called(e, "assess_risk", ESTABLISHED)),
            ("gives recommendations", lambda r, e: len(r.narrative.recommendations) >= 1),
        ],
    ),
    Case(
        "closed_company",
        CLOSED,
        "Buy construction materials",
        [
            ("risk level CRITICAL", lambda r, e: r.risk.level == "CRITICAL"),
            (
                "summary says it is closed",
                lambda r, e: mentions(r, "closed", "baixada", "inactive"),
            ),
            ("advises against proceeding", lambda r, e: mentions(r, "do not", "avoid", "cannot")),
        ],
    ),
    Case(
        "new_company_for_electrical_work",
        NEW_TINY,
        "Hire a company for the electrical refurbishment of an industrial warehouse",
        [
            ("risk level MEDIUM", lambda r, e: r.risk.level == "MEDIUM"),
            (
                "flags the activity mismatch (office support services)",
                lambda r, e: r.narrative.activity_fit in ("incompatible", "partial"),
            ),
            ("mentions the company's age", lambda r, e: mentions(r, "month", "new", "recent")),
        ],
    ),
    Case(
        "no_purpose_given",
        ESTABLISHED,
        None,
        [
            (
                "activity_fit is not_evaluated",
                lambda r, e: r.narrative.activity_fit == "not_evaluated",
            )
        ],
    ),
    Case(
        "company_on_ceis_debarment_list",
        ESTABLISHED,
        "Hire a contractor to build a warehouse",
        [
            ("risk level CRITICAL", lambda r, e: r.risk.level == "CRITICAL"),
            ("narrative cites CEIS", lambda r, e: "ceis" in prose(r)),
            ("never calls it clean", lambda r, e: "no sanction" not in r.narrative.summary.lower()),
        ],
        sanctioned={ESTABLISHED},
    ),
]


async def run_case(client: anthropic.AsyncAnthropic, case: Case) -> dict[str, Any]:
    settings = get_settings()
    events: Events = []

    async def emit(event: dict[str, Any]) -> None:
        events.append(event)

    agent = DueDiligenceAgent(
        client,
        FixtureData(case.sanctioned),  # type: ignore[arg-type]
        model=settings.claude_model,
        effort=settings.claude_effort,
        max_turns=settings.max_agent_turns,
    )
    started = time.perf_counter()
    try:
        report = await agent.run(case.cnpj, case.purpose, emit)
    except Exception as exc:  # an agent crash fails every check of the case
        return {"case": case.name, "error": repr(exc), "checks": {n: False for n, _ in case.checks}}

    return {
        "case": case.name,
        "seconds": round(time.perf_counter() - started, 1),
        "tool_calls": sum(1 for e in events if e["type"] == "tool_call"),
        "checks": {name: bool(check(report, events)) for name, check in case.checks},
        "narrative": report.narrative.model_dump(),
    }


async def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; evals make real Claude API calls.")
        return 2

    client = anthropic.AsyncAnthropic()
    results = await asyncio.gather(*(run_case(client, c) for c in CASES))

    passed = total = 0
    for result in results:
        seconds, calls = result.get("seconds", "-"), result.get("tool_calls", 0)
        print(f"\n{result['case']}  ({seconds}s, {calls} tool calls)")
        if "error" in result:
            print(f"  ERROR: {result['error']}")
        for name, ok in result["checks"].items():
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            passed += ok
            total += 1

    score = passed / total
    print(f"\nScore: {passed}/{total} ({score:.0%})")

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    payload = {"model": get_settings().claude_model, "score": score, "results": results}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved to {out}")
    return 0 if score >= PASS_THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
