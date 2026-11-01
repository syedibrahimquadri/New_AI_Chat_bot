"""Scrape allowlisted public pages and save raw HTML."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from src.ingest.sources import Source, allowed_sources, is_url_allowed, load_sources
from src.utils.config import ensure_directories

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.5
USER_AGENT = (
    "Mozilla/5.0 (compatible; MF-FAQ-RAG-Demo/1.0; +https://groww.in) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ScrapeResult:
    source_id: str
    url: str
    ok: bool
    path: str | None = None
    error: str | None = None
    kept_previous: bool = False
    bytes_written: int = 0


@dataclass
class ScrapeReport:
    results: list[ScrapeResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.ok)

    def summary(self) -> str:
        lines = [
            f"Scrape complete: {self.success_count} ok, {self.failure_count} failed "
            f"(total {len(self.results)})"
        ]
        for r in self.results:
            if r.ok:
                lines.append(f"  OK  id={r.source_id} -> {r.path} ({r.bytes_written} bytes)")
            else:
                kept = " (kept previous)" if r.kept_previous else ""
                lines.append(f"  FAIL id={r.source_id} {r.url}: {r.error}{kept}")
        return "\n".join(lines)


def fetch_html(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> str:
    last_error: Exception | None = None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }

    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for attempt in range(1, retries + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
                return response.text
            except Exception as exc:  # noqa: BLE001 - collect and retry network/HTTP errors
                last_error = exc
                logger.warning(
                    "Fetch attempt %s/%s failed for %s: %s",
                    attempt,
                    retries,
                    url,
                    exc,
                )
                if attempt < retries:
                    time.sleep(backoff * attempt)

    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_error}")


def save_raw(raw_dir: Path, source_id: str, html: str) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = raw_dir / f"{source_id}.html"
    out.write_text(html, encoding="utf-8")
    return out


def run_scrape(settings: dict[str, Any]) -> ScrapeReport:
    ensure_directories(settings)
    raw_dir = Path(settings["paths"]["raw"])
    sources = load_sources(settings["sources_file"])
    to_fetch = allowed_sources(sources)

    scrape_cfg = settings.get("scrape", {})
    timeout = float(scrape_cfg.get("timeout", DEFAULT_TIMEOUT))
    retries = int(scrape_cfg.get("retries", DEFAULT_RETRIES))
    backoff = float(scrape_cfg.get("backoff", DEFAULT_BACKOFF))

    report = ScrapeReport()
    for source in to_fetch:
        report.results.append(
            _scrape_one(
                source=source,
                all_sources=sources,
                raw_dir=raw_dir,
                timeout=timeout,
                retries=retries,
                backoff=backoff,
            )
        )
    return report


def _scrape_one(
    *,
    source: Source,
    all_sources: list[Source],
    raw_dir: Path,
    timeout: float,
    retries: int,
    backoff: float,
) -> ScrapeResult:
    previous = raw_dir / f"{source.id}.html"

    if not is_url_allowed(source.url, all_sources):
        return ScrapeResult(
            source_id=source.id,
            url=source.url,
            ok=False,
            error="URL not in allowlist",
            kept_previous=previous.is_file(),
        )

    host = urlparse(source.url).netloc.lower()
    if not host:
        return ScrapeResult(
            source_id=source.id,
            url=source.url,
            ok=False,
            error="Invalid URL host",
            kept_previous=previous.is_file(),
        )

    try:
        html = fetch_html(source.url, timeout=timeout, retries=retries, backoff=backoff)
        if not html.strip():
            raise RuntimeError("Empty HTML body")
        path = save_raw(raw_dir, source.id, html)
        return ScrapeResult(
            source_id=source.id,
            url=source.url,
            ok=True,
            path=str(path),
            bytes_written=path.stat().st_size,
        )
    except Exception as exc:  # noqa: BLE001
        return ScrapeResult(
            source_id=source.id,
            url=source.url,
            ok=False,
            error=str(exc),
            kept_previous=previous.is_file(),
            path=str(previous) if previous.is_file() else None,
        )
