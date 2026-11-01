"""Chat API: uvicorn backend.main:app --port 8000"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.generate.answer import answer_question
from src.generate.guardrails import classify
from src.ingest.embed import get_model
from src.llm.base import LLMError
from src.retrieve.retriever import find_schemes
from src.utils.config import load_settings

ROOT = Path(__file__).resolve().parents[1]
settings = load_settings()

app = FastAPI(title="FundFacts API")
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["POST"], allow_headers=["*"]
    )


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    last_scheme: str | None = Field(default=None, max_length=80)


@app.on_event("startup")
def warm_up() -> None:
    threading.Thread(target=get_model, args=(settings,), daemon=True).start()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    question = request.question.strip()
    named = find_schemes(question, settings)
    known = {s for s in find_schemes(request.last_scheme or "", settings)}
    scheme = named[0] if named else (request.last_scheme if request.last_scheme in known else None)
    if not named and scheme and classify(question, []) == "needs_scheme":
        # Follow-up such as "what about its exit load?": reuse the fund in discussion.
        question = f"{question} for {scheme}"

    try:
        result = answer_question(question, settings)
    except (LLMError, RuntimeError) as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})
    return {
        "type": result.type,
        "text": result.text,
        "citation_url": result.citation_url,
        "last_updated": result.last_updated_from_sources,
        "last_scheme": scheme,
    }


# Lets the API host serve the page too, for local testing or as a fallback.
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
