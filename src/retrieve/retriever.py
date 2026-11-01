"""Stage 6: embed a question with the ingestion model and query the vector DB."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ingest.embed import get_collection, get_model

_EXTRA_ALIASES = {"tax saver": "HDFC ELSS", "flexicap": "HDFC Flexi Cap", "hdfc equity": "HDFC Flexi Cap"}


def _scheme_aliases(settings: dict[str, Any]) -> dict[str, str]:
    """Map lowercase scheme names found in sources.csv to their scheme label."""
    aliases = dict(_EXTRA_ALIASES)
    with open(settings["sources_file"], encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            scheme = row["scheme"]
            if scheme.startswith("HDFC ") and scheme != "HDFC MF":
                aliases[scheme.removeprefix("HDFC ").lower()] = scheme
                aliases[scheme.removesuffix(" Index").removeprefix("HDFC ").lower()] = scheme
    return aliases


def find_schemes(question: str, settings: dict[str, Any]) -> list[str]:
    """Return schemes named in the question, in order of first mention."""
    lowered = question.lower()
    hits: list[tuple[int, str]] = []
    # Longest first, so "nifty next 50" is not also read as a shorter alias.
    for alias, scheme in sorted(_scheme_aliases(settings).items(), key=lambda a: -len(a[0])):
        match = re.search(rf"\b{re.escape(alias)}\b", lowered)
        if match:
            hits.append((match.start(), scheme))
            lowered = lowered.replace(alias, " " * len(alias))
    ordered: list[str] = []
    for _, scheme in sorted(hits):
        if scheme not in ordered:
            ordered.append(scheme)
    return ordered


def retrieve(
    question: str,
    settings: dict[str, Any],
    scheme: str | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    collection = get_collection(settings)
    if collection.count() == 0:
        raise RuntimeError("Vector DB is empty. Run: python -m src.ingest.pipeline --stage all")

    vector = get_model(settings).encode([question], normalize_embeddings=True).tolist()
    result = collection.query(
        query_embeddings=vector,
        n_results=top_k or int(settings["retrieval"]["top_k"]),
        where={"scheme": scheme} if scheme else None,
    )
    hits = [
        {"chunk_id": i, "text": t, "distance": round(d, 4), **m}
        for i, t, d, m in zip(
            result["ids"][0], result["documents"][0], result["distances"][0], result["metadatas"][0]
        )
    ]
    _log(question, scheme, hits, settings)
    return hits


def _log(
    question: str, scheme: str | None, hits: list[dict[str, Any]], settings: dict[str, Any]
) -> None:
    """Demo artifact. Only reached after the PII check has passed."""
    log_dir = Path(settings["paths"]["retrieval_logs"])
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    payload = {"question": question, "scheme_filter": scheme, "hits": hits}
    (log_dir / f"{stamp}.json").write_text(json.dumps(payload, indent=2), "utf-8")
