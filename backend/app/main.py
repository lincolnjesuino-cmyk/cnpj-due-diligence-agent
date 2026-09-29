import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

import anthropic
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agent import AgentError, DueDiligenceAgent
from app.cnpj import InvalidCNPJError, normalize
from app.config import get_settings
from app.sources import CompanyNotFoundError, PublicDataClient, SourceUnavailableError

logger = logging.getLogger("due_diligence")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.http = httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": "cnpj-due-diligence-agent/0.1"},
    )
    app.state.claude = anthropic.AsyncAnthropic()
    yield
    await app.state.http.aclose()
    await app.state.claude.close()


app = FastAPI(title="CNPJ Due Diligence Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    cnpj: str
    purpose: str | None = Field(default=None, max_length=500)
    language: Literal["en", "pt"] = "en"


@app.get("/api/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "model": settings.claude_model,
        "sanctions_source_configured": bool(settings.portal_transparencia_api_key),
    }


@app.post("/api/analyze")
async def analyze(body: AnalyzeRequest) -> EventSourceResponse:
    try:
        cnpj = normalize(body.cnpj)
    except InvalidCNPJError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    settings = get_settings()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def emit(event: dict[str, Any]) -> None:
        await queue.put(event)

    async def work() -> None:
        agent = DueDiligenceAgent(
            client=app.state.claude,
            data=PublicDataClient(app.state.http, settings.portal_transparencia_api_key),
            model=settings.claude_model,
            effort=settings.claude_effort,
            max_turns=settings.max_agent_turns,
        )
        try:
            await agent.run(cnpj, body.purpose, emit, body.language)
        except (CompanyNotFoundError, AgentError, SourceUnavailableError) as exc:
            await emit({"type": "error", "message": str(exc)})
        except anthropic.AuthenticationError:
            await emit({"type": "error", "message": "Anthropic API key is missing or invalid."})
        except anthropic.RateLimitError:
            await emit({"type": "error", "message": "API rate limit reached. Try again shortly."})
        except anthropic.APIStatusError as exc:
            logger.exception("Claude API error")
            await emit({"type": "error", "message": f"Claude API error (HTTP {exc.status_code})."})
        except anthropic.APIConnectionError:
            await emit({"type": "error", "message": "Could not reach the Claude API."})
        finally:
            await queue.put(None)

    async def stream() -> AsyncIterator[dict[str, str]]:
        task = asyncio.create_task(work())
        try:
            while (event := await queue.get()) is not None:
                yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
        finally:
            task.cancel()

    return EventSourceResponse(stream())
