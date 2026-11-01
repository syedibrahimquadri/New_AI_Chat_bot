"""Stage 3: split cleaned documents into section-aware chunks."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


def _split_sized(text: str, size: int, overlap: int) -> list[str]:
    """Fixed-size split that prefers to break at a newline or sentence end."""
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start + size // 2 : end]
            breaks = [m.end() for m in re.finditer(r"\n|\. ", window)]
            if breaks:
                end = start + size // 2 + breaks[-1]
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in pieces if p]


# Fund documents list "Label: value" lines; each label belongs to one FAQ topic.
_FACT_SECTIONS = {
    "Expense ratio": "Expense ratio",
    "Base expense ratio": "Expense ratio",
    "Exit load": "Exit load",
    "Lock-in": "Lock-in period",
    "Minimum SIP": "Minimum SIP and lumpsum",
    "SIP allowed": "Minimum SIP and lumpsum",
    "Minimum lump sum investment": "Minimum SIP and lumpsum",
    "Minimum additional investment": "Minimum SIP and lumpsum",
    "Minimum withdrawal": "Minimum SIP and lumpsum",
    "Riskometer / risk": "Riskometer",
    "Benchmark": "Benchmark",
    "Fund size (AUM)": "Fund size and NAV",
    "NAV": "Fund size and NAV",
}


def _fact_sections(text: str) -> list[tuple[str, str]]:
    """Group a fund document's fact lines by topic; other blocks keep their heading."""
    blocks = text.split("\n\n")
    grouped: dict[str, list[str]] = {}
    # A blank line inside a value (seen in exit_load) can split the fact list in two.
    fact_lines = [
        line
        for block in blocks
        if re.match(r"[A-Z][\w /-]*: \S", block)
        for line in block.splitlines()
    ]
    blocks = [b for b in blocks if not re.match(r"[A-Z][\w /-]*: \S", b)]
    for line in fact_lines:
        label = line.split(":", 1)[0].strip()
        if label != "Source page":
            grouped.setdefault(_FACT_SECTIONS.get(label, "Fund details"), []).append(line)
    pairs = [(title, "\n".join(lines)) for title, lines in grouped.items()]
    for block in blocks:
        first, _, rest = block.partition("\n")
        if first.endswith(":") and rest.strip():
            pairs.append((first.rstrip(":"), rest.strip()))
        elif block.strip():
            pairs.append(("Notes", block.strip()))
    return pairs


def _amc_sections(text: str) -> list[tuple[str, str]]:
    """Give every key-information fact its own chunk so short lookups can find it."""
    pairs: list[tuple[str, str]] = []
    rest: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        fact = re.match(r"- (\w+): (.+)", line)
        if fact:
            label = fact.group(1).replace("_", " ").title()
            if label.lower() in seen or label in ("Search Id", "Fund House", "Total Aum"):
                continue
            seen.add(label.lower())
            value = fact.group(2).strip()
            pairs.append((label, f"The {label} of HDFC Mutual Fund is {value}."))
        elif not line.startswith(("AMC overview:", "Scheme label:", "Source page:", "Key information")):
            rest.append(line)
    body = "\n".join(rest).strip()
    return pairs + ([("About HDFC Mutual Fund", body)] if body else [])


def _sections(text: str) -> list[tuple[str, str]]:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    if text.startswith("Scheme:"):
        return _fact_sections(text)
    if text.startswith("AMC overview:"):
        return _amc_sections(text)
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    pairs = [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]
    return [p for p in pairs if p[1]] or [("Document", text.strip())]


def chunk(settings: dict[str, Any]) -> dict[str, int]:
    cfg = settings["chunking"]
    size, overlap = int(cfg["chunk_size"]), int(cfg["chunk_overlap"])
    in_dir = Path(settings["paths"]["cleaned"])
    out_dir = Path(settings["paths"]["chunks"])
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jsonl"):
        old.unlink()

    counts: dict[str, int] = {}
    for meta_path in sorted(in_dir.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text("utf-8"))
        text = (in_dir / f"{meta['doc_id']}.txt").read_text("utf-8")
        if cfg["strategy"] == "section_recursive":
            sections = _sections(text)
        else:
            sections = [("Document", text)]
        records = []
        for section, body in sections:
            for piece in _split_sized(body, size, overlap):
                records.append(
                    {
                        "chunk_id": f"{meta['doc_id']}-{len(records):03d}",
                        # Heading stays in the text so it is part of the embedding.
                        "text": f"{meta['title']} - {section}\n{piece}",
                        "section": section,
                        "doc_id": meta["doc_id"],
                        "title": meta["title"],
                        "scheme": meta["scheme"],
                        "source_url": meta["source_url"],
                        "scraped_at": meta["scraped_at"],
                    }
                )
        with (out_dir / f"{meta['doc_id']}.jsonl").open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        counts[meta["doc_id"]] = len(records)
    print(f"  {sum(counts.values())} chunks from {len(counts)} documents")
    return counts
