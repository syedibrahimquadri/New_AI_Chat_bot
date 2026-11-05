"""Question to cited answer: python -m src.generate.answer --q "..." """

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from src.ingest.sources import allowed_sources, load_sources
from src.generate.guardrails import AMC_URL, EDUCATION_URL, MESSAGES, classify
from src.generate.prompts import SYSTEM_PROMPT, build_user_prompt
from src.llm.base import LLMClient, LLMError, get_client
from src.retrieve.retriever import find_schemes, retrieve
from src.utils.config import load_settings

NOT_FOUND = "I could not find that in my sources."
CAS_URL = "https://investor.sebi.gov.in/consolidated_account_statement.html"
_CAPITAL_GAINS = re.compile(r"\bcapital[- ]gains?\b", re.I)
_AMC_TOPIC = re.compile(
    r"\b(officer|ceo|cio|md|managing director|trustees?|sponsors?|total aum|"
    r"address|incorporat\w+|asset management company)\b",
    re.I,
)
_ADVICE_OUTPUT = re.compile(r"\b(you should (?:buy|sell|hold|invest|redeem|switch)|i recommend|we recommend|good investment)\b", re.I)


@dataclass
class Answer:
    type: str  # answer | refusal | not_found
    text: str
    citation_url: str | None = None
    last_updated_from_sources: str | None = None
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    hits: list[dict[str, Any]] = field(default_factory=list)


def _scheme_url(scheme: str | None, settings: dict[str, Any]) -> str:
    if scheme:
        hits = retrieve(scheme, settings, scheme=scheme)
        if hits:
            return hits[0]["source_url"]
    return AMC_URL


def _trim(text: str, max_sentences: int) -> str:
    text = re.sub(r"https?://\S+", "", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:max_sentences]).strip()


def _parse(raw: str) -> dict[str, Any] | None:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


# "What sources do you use?" is about the assistant, so no page answers it.
_SOURCES_Q = re.compile(
    r"\b(what|which|list|show|name|tell|how many|give)\b.*\b(sources|links|urls|websites|pages|documents|references)\b"
    r"|\b(your|you)\b.*\b(sources?|links?|urls?|websites?|data|corpus|trained)\b",
    re.I,
)
SOURCES_LIST_URL = (
    "https://github.com/syedibrahimquadri/New_AI_Chat_bot/blob/main/data/sources.csv"
)


def _sources_answer(settings: dict[str, Any]) -> Answer:
    sources = allowed_sources(load_sources(settings["sources_file"]))
    groww = [s for s in sources if "groww.in" in s.url]
    sebi = [s for s in sources if "sebi.gov.in" in s.url]
    amfi = [s for s in sources if "amfiindia.com" in s.url]
    funds = ", ".join(s.scheme for s in groww if s.scheme and "AMC" not in s.title)
    text = (
        f"I answer only from {len(sources)} public pages: {len(groww)} HDFC Mutual Fund pages on Groww, "
        f"{len(sebi)} SEBI investor pages and {len(amfi)} AMFI pages. "
        f"The schemes covered are {funds}. "
        "The SEBI and AMFI pages cover the riskometer, exit load, ELSS, KYC and account statements."
    )
    return Answer("answer", text, citation_url=SOURCES_LIST_URL)


def answer_question(
    question: str, settings: dict[str, Any], llm: LLMClient | None = None
) -> Answer:
    question = question.strip()
    schemes = find_schemes(question, settings)
    intent = classify(question, schemes)
    if intent == "factual" and not schemes and _SOURCES_Q.search(question):
        return _sources_answer(settings)

    if intent != "factual":
        if intent == "pii":
            url = None
        elif intent == "performance":
            url = _scheme_url(schemes[0] if schemes else None, settings)
        elif intent in ("advice", "prediction"):
            url = EDUCATION_URL
        else:
            url = AMC_URL
        return Answer("refusal", MESSAGES[intent], citation_url=url)

    # A question naming several schemes is answered for the first, so one link stays accurate.
    if _CAPITAL_GAINS.search(question):
        # No source explains this, and models tend to stretch the CAS page to fit.
        return Answer("not_found", NOT_FOUND, citation_url=CAS_URL)

    scheme = schemes[0] if schemes else None
    if not scheme and _AMC_TOPIC.search(question):
        scheme = "HDFC MF"
    # AMC facts are many short chunks, so read all of them for these questions.
    # A fund or the AMC has only a few short chunks, so read them all rather than
    # risk ranking the right one out of the top results.
    hits = retrieve(question, settings, scheme=scheme, top_k=14 if scheme else None)
    ids = [h["chunk_id"] for h in hits]
    if not hits:
        return Answer("not_found", NOT_FOUND, citation_url=AMC_URL)

    client = llm or get_client(settings)
    max_sentences = int(settings["generation"]["max_sentences"])
    raw = client.complete(
        SYSTEM_PROMPT.format(max_sentences=max_sentences), build_user_prompt(question, hits)
    )
    data = _parse(raw)
    source = data.get("source") if data else None
    valid = (
        data is not None
        and data.get("found") is True
        and isinstance(source, int)
        and 1 <= source <= len(hits)
        and str(data.get("answer") or "").strip()
    )
    if not valid or _ADVICE_OUTPUT.search(str(data.get("answer"))):
        return Answer("not_found", NOT_FOUND, AMC_URL, None, ids, hits)

    # Link and date come from chunk metadata, never from model text.
    chosen = hits[source - 1]
    return Answer(
        "answer",
        _trim(str(data["answer"]), max_sentences),
        chosen["source_url"],
        chosen["scraped_at"],
        ids,
        hits,
    )


def format_answer(result: Answer) -> str:
    lines = [result.text]
    if result.citation_url:
        lines.append(f"Source: {result.citation_url}")
    if result.last_updated_from_sources:
        lines.append(f"Last updated from sources: {result.last_updated_from_sources}")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--q", required=True)
    args = parser.parse_args()
    try:
        output = answer_question(args.q, load_settings())
    except (LLMError, RuntimeError) as exc:
        raise SystemExit(f"Error: {exc}") from exc
    print(format_answer(output))
    print(json.dumps({k: v for k, v in asdict(output).items() if k != "hits"}, indent=2))
