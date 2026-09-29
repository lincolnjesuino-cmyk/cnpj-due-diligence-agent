"""Due diligence agent: Claude orchestrates public-data tools and writes the narrative.

Design rule: facts (company data, sanctions, risk score) are produced by code from public
sources. The model decides *what to investigate* and *how to explain it*, but it cannot
change a fact or the risk level. That keeps every report auditable.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import anthropic

from app.cnpj import InvalidCNPJError, normalize
from app.models import CompanyProfile, Narrative, Report, SanctionsResult
from app.risk import assess
from app.sources import CompanyNotFoundError, PublicDataClient, SourceUnavailableError

EventSink = Callable[[dict[str, Any]], Awaitable[None]]
Language = Literal["en", "pt"]

MAX_RELATED_COMPANIES = 3
LANGUAGE_NAMES: dict[Language, str] = {"en": "English", "pt": "Brazilian Portuguese"}

SYSTEM_PROMPT = """\
You are a due diligence analyst for Brazilian companies (KYB / vendor screening). You \
investigate one CNPJ (the Brazilian company registration number) using only the tools \
provided, which query official public data, and you write an objective assessment for \
someone deciding whether to hire, buy from, or partner with that company.

How to investigate:
- Always call `lookup_company` and `check_sanctions` for the target CNPJ, in the same turn.
- If a shareholder is itself a company (14-digit document), investigate up to \
{max_related} of those shareholder companies with the same tools: problems there are \
risks for the target too.
- After looking up the target, call `assess_risk` for the target CNPJ. It applies the \
system's fixed risk rules to the data already retrieved and returns the level and signals.
- Never invent facts. Every claim must come from a tool result. If a source could not be \
checked, say so explicitly.

The risk level shown next to your analysis comes from `assess_risk`. Do not assign a \
different score or level; explain the returned signals and what they mean in practice, \
without contradicting them.

About `activity_fit`: compare the registered activities (primary and secondary CNAE \
codes) with the user's stated purpose. Use `not_evaluated` when no purpose is given.

Registry values such as company names, status ("ATIVA" = active, "BAIXADA" = closed) and \
activity descriptions are in Portuguese; you may quote them, but write your analysis in \
{language}. Your final answer is the requested JSON, in short, concrete sentences. In \
`recommendations`, suggest verifiable next steps (e.g. which certificates to request).\
"""

_CNPJ_INPUT = {
    "type": "object",
    "properties": {"cnpj": {"type": "string", "description": "CNPJ, with or without punctuation."}},
    "required": ["cnpj"],
    "additionalProperties": False,
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "lookup_company",
        "description": (
            "Returns a company's registration record from Receita Federal (via BrasilAPI): "
            "legal name, registration status, opening date, share capital, activity codes "
            "(CNAE) and shareholders (QSA). Use it for the target and for shareholder companies."
        ),
        "strict": True,
        "input_schema": _CNPJ_INPUT,
    },
    {
        "name": "check_sanctions",
        "description": (
            "Checks Brazil's federal debarment lists on Portal da Transparência: CEIS "
            "(companies barred from public contracts) and CNEP (companies punished under the "
            "Anti-Corruption Law). Returns `checked: false` when the source is unavailable."
        ),
        "strict": True,
        "input_schema": _CNPJ_INPUT,
    },
    {
        "name": "assess_risk",
        "description": (
            "Applies the system's fixed risk rules to the data already retrieved for a CNPJ "
            "(status, sanctions, age, share capital, shareholders) and returns the score, the "
            "level (LOW, MEDIUM, HIGH, CRITICAL) and each signal with its source."
        ),
        "strict": True,
        "input_schema": _CNPJ_INPUT,
    },
]

NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "activity_fit": {
            "type": "string",
            "enum": ["compatible", "partial", "incompatible", "not_evaluated"],
        },
        "activity_fit_reason": {"type": "string"},
        "attention_points": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "activity_fit",
        "activity_fit_reason",
        "attention_points",
        "recommendations",
    ],
    "additionalProperties": False,
}


class AgentError(RuntimeError):
    pass


def _company_for_model(profile: CompanyProfile) -> dict[str, Any]:
    """Compact view of the profile: fewer tokens, same facts."""
    data = profile.model_dump(mode="json", exclude_none=True)
    data["partners"] = [
        {**p.model_dump(mode="json", exclude_none=True), "is_company": p.is_company}
        for p in profile.partners
    ]
    return data


class DueDiligenceAgent:
    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        data: PublicDataClient,
        model: str,
        effort: str = "medium",
        max_turns: int = 12,
    ) -> None:
        self._client = client
        self._data = data
        self._model = model
        self._effort = effort
        self._max_turns = max_turns
        self._companies: dict[str, CompanyProfile] = {}
        self._sanctions: dict[str, SanctionsResult] = {}

    async def _facts(self, cnpj: str) -> tuple[CompanyProfile, SanctionsResult]:
        if cnpj not in self._companies:
            self._companies[cnpj] = await self._data.company(cnpj)
        if cnpj not in self._sanctions:
            self._sanctions[cnpj] = await self._data.sanctions(cnpj)
        return self._companies[cnpj], self._sanctions[cnpj]

    async def _run_tool(self, name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
        """Execute one tool call. Returns (content, is_error)."""
        try:
            cnpj = normalize(str(tool_input.get("cnpj", "")))
            if name == "lookup_company":
                if cnpj not in self._companies:
                    self._companies[cnpj] = await self._data.company(cnpj)
                profile = _company_for_model(self._companies[cnpj])
                return json.dumps(profile, ensure_ascii=False), False
            if name == "check_sanctions":
                if cnpj not in self._sanctions:
                    self._sanctions[cnpj] = await self._data.sanctions(cnpj)
                return self._sanctions[cnpj].model_dump_json(exclude_none=True), False
            if name == "assess_risk":
                company, sanctions = await self._facts(cnpj)
                return assess(company, sanctions).model_dump_json(), False
            return f"Unknown tool: {name}", True
        except (InvalidCNPJError, CompanyNotFoundError, SourceUnavailableError) as exc:
            return str(exc), True

    async def run(
        self,
        cnpj: str,
        purpose: str | None,
        emit: EventSink,
        language: Language = "en",
    ) -> Report:
        target = normalize(cnpj)
        stated = purpose.strip() if purpose and purpose.strip() else "not provided"
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": f"Target CNPJ: {target}.\nUser's purpose: {stated}"}
        ]
        system = SYSTEM_PROMPT.format(
            max_related=MAX_RELATED_COMPANIES, language=LANGUAGE_NAMES[language]
        )

        for _ in range(self._max_turns):
            response = await self._client.beta.messages.create(
                model=self._model,
                max_tokens=16000,
                system=system,
                tools=TOOLS,
                messages=messages,
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": NARRATIVE_SCHEMA},
                },
                # If a safety classifier declines, the API retries on a fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )

            if response.stop_reason == "refusal":
                raise AgentError("The model refused the request.")
            if response.stop_reason == "max_tokens":
                raise AgentError("The model response was truncated (max_tokens).")

            # Append the full content so thinking blocks are passed back unchanged.
            messages.append({"role": "assistant", "content": response.content})

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_calls:
                text = next((b.text for b in response.content if b.type == "text"), "")
                return await self._build_report(target, text, language, emit)

            for call in tool_calls:
                await emit({"type": "tool_call", "tool": call.name, "input": call.input})
            results = await asyncio.gather(*(self._run_tool(c.name, c.input) for c in tool_calls))
            for call, (_, is_error) in zip(tool_calls, results, strict=True):
                await emit(
                    {
                        "type": "tool_result",
                        "tool": call.name,
                        "input": call.input,
                        "ok": not is_error,
                    }
                )

            # All results go back in a single user message (keeps parallel tool use working).
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "content": content,
                            "is_error": is_error,
                        }
                        for call, (content, is_error) in zip(tool_calls, results, strict=True)
                    ],
                }
            )

        raise AgentError(f"The agent exceeded the limit of {self._max_turns} turns.")

    async def _build_report(
        self, target: str, final_text: str, language: Language, emit: EventSink
    ) -> Report:
        try:
            narrative = Narrative.model_validate_json(final_text)
        except ValueError as exc:
            raise AgentError("The model's final answer did not match the expected format.") from exc

        # Guarantee: the facts in the report come from code, even if the model skipped a tool.
        company, sanctions = await self._facts(target)
        report = Report(
            company=company,
            sanctions=sanctions,
            risk=assess(company, sanctions),
            narrative=narrative,
            related_companies=[p for c, p in self._companies.items() if c != target],
            sources=self._data.consulted,
            model=self._model,
            language=language,
        )
        await emit({"type": "report", "report": report.model_dump(mode="json")})
        return report
