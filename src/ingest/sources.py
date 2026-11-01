"""Load allowlisted sources from CSV."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    scheme: str
    category: str
    url: str
    allowed: bool


def load_sources(sources_file: str | Path) -> list[Source]:
    path = Path(sources_file)
    if not path.is_file():
        raise FileNotFoundError(f"Sources file not found: {path}")

    sources: list[Source] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"id", "title", "scheme", "category", "url", "allowed"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"sources.csv must include columns: {sorted(required)}")

        for row in reader:
            allowed = str(row["allowed"]).strip().lower() in {"true", "1", "yes"}
            sources.append(
                Source(
                    id=str(row["id"]).strip(),
                    title=str(row["title"]).strip(),
                    scheme=str(row["scheme"]).strip(),
                    category=str(row["category"]).strip(),
                    url=str(row["url"]).strip(),
                    allowed=allowed,
                )
            )
    return sources


def allowed_sources(sources: list[Source]) -> list[Source]:
    return [s for s in sources if s.allowed]


def allowed_hosts(sources: list[Source]) -> set[str]:
    hosts: set[str] = set()
    for source in allowed_sources(sources):
        host = urlparse(source.url).netloc.lower()
        if host:
            hosts.add(host)
    return hosts


def is_url_allowed(url: str, sources: list[Source]) -> bool:
    """URL must match an allowlisted source URL exactly (public pages only)."""
    normalized = url.strip()
    return any(s.allowed and s.url == normalized for s in sources)
