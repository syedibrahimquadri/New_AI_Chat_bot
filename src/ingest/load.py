"""Load scraped HTML into cleaned documents + metadata."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.ingest.sources import Source, allowed_sources, load_sources
from src.utils.config import ensure_directories

logger = logging.getLogger(__name__)

DEFAULT_MIN_CHARS = 80
NOISE_TAGS = ("script", "style", "noscript", "svg", "iframe")
NOISE_SELECTORS = ("nav", "footer", "header")


@dataclass
class Document:
    doc_id: str
    title: str
    scheme: str
    source_url: str
    text: str
    scraped_at: str
    category: str = ""
    char_count: int = 0
    status: str = "ok"
    extract_method: str = "html_text"

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


@dataclass
class LoadResult:
    doc_id: str
    ok: bool
    path_txt: str | None = None
    path_meta: str | None = None
    error: str | None = None
    char_count: int = 0
    extract_method: str | None = None


@dataclass
class LoadReport:
    results: list[LoadResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.ok)

    def summary(self) -> str:
        lines = [
            f"Load complete: {self.success_count} ok, {self.failure_count} failed "
            f"(total {len(self.results)})"
        ]
        for r in self.results:
            if r.ok:
                lines.append(
                    f"  OK  id={r.doc_id} chars={r.char_count} "
                    f"method={r.extract_method} -> {r.path_txt}"
                )
            else:
                lines.append(f"  FAIL id={r.doc_id}: {r.error}")
        return "\n".join(lines)


def run_load(settings: dict[str, Any]) -> LoadReport:
    ensure_directories(settings)
    raw_dir = Path(settings["paths"]["raw"])
    cleaned_dir = Path(settings["paths"]["cleaned"])
    min_chars = int(settings.get("load", {}).get("min_chars", DEFAULT_MIN_CHARS))

    sources = allowed_sources(load_sources(settings["sources_file"]))
    report = LoadReport()

    for source in sources:
        report.results.append(
            _load_one(source, raw_dir=raw_dir, cleaned_dir=cleaned_dir, min_chars=min_chars)
        )
    return report


def _load_one(
    source: Source,
    *,
    raw_dir: Path,
    cleaned_dir: Path,
    min_chars: int,
) -> LoadResult:
    raw_path = raw_dir / f"{source.id}.html"
    if not raw_path.is_file():
        return LoadResult(doc_id=source.id, ok=False, error=f"Missing raw file: {raw_path}")

    try:
        html = raw_path.read_text(encoding="utf-8")
        scraped_at = datetime.fromtimestamp(raw_path.stat().st_mtime, tz=timezone.utc).date().isoformat()
        text, method = extract_document_text(html, source)
        text = normalize_whitespace(text)

        if len(text) < min_chars:
            return LoadResult(
                doc_id=source.id,
                ok=False,
                error=f"Document too short ({len(text)} < {min_chars} chars)",
                extract_method=method,
                char_count=len(text),
            )

        doc = Document(
            doc_id=source.id,
            title=source.title,
            scheme=source.scheme,
            source_url=source.url,
            text=text,
            scraped_at=scraped_at,
            category=source.category,
            extract_method=method,
        )
        txt_path, meta_path = save_cleaned(cleaned_dir, doc)
        return LoadResult(
            doc_id=source.id,
            ok=True,
            path_txt=str(txt_path),
            path_meta=str(meta_path),
            char_count=doc.char_count,
            extract_method=method,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed loading id=%s", source.id)
        return LoadResult(doc_id=source.id, ok=False, error=str(exc))


def extract_document_text(html: str, source: Source) -> tuple[str, str]:
    """Return (text, extract_method). Prefer Groww JSON facts when available."""
    soup = BeautifulSoup(html, "lxml")
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        try:
            payload = json.loads(next_data.string)
            page_props = payload.get("props", {}).get("pageProps", {})
            if "mfServerSideData" in page_props:
                return (
                    format_fund_document(page_props["mfServerSideData"], source),
                    "groww_mf_json",
                )
            if "amcMainPageData" in page_props:
                return (
                    "\n".join(
                        [
                            format_amc_document(page_props["amcMainPageData"], source),
                            *key_info_lines(soup),
                        ]
                    ),
                    "groww_amc_json",
                )
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.warning("NEXT_DATA parse failed for %s: %s", source.id, exc)

    return html_to_text(soup), "html_text"


def format_fund_document(data: dict[str, Any], source: Source) -> str:
    """Build a facts-focused plain-text doc. Omits return/performance series."""
    lock_in = format_lock_in(data.get("lock_in"))
    # nfo_risk is stale on Groww; the page displays the rating held in meta_desc.
    risk_match = re.search(r"Risk is ([A-Za-z ]+?)\s*$", data.get("meta_desc") or "")
    risk = risk_match.group(1) if risk_match else "Not stated"
    fund_managers = format_fund_managers(data.get("fund_manager_details") or data.get("fund_manager"))

    lines = [
        f"Scheme: {data.get('scheme_name') or source.title}",
        f"Fund house / AMC: {data.get('fund_house') or data.get('amc') or 'HDFC Mutual Fund'}",
        f"Category: {data.get('category') or ''}",
        f"Sub category: {data.get('sub_category') or ''}",
        f"Plan type: {data.get('plan_type') or ''}",
        f"Scheme type: {data.get('scheme_type') or ''}",
        f"Benchmark: {data.get('benchmark') or data.get('benchmark_name') or 'Not stated'}",
        f"Riskometer / risk: {risk}",
        f"Expense ratio: {data.get('expense_ratio')}%",
        f"Base expense ratio: {data.get('base_expense_ratio')}%",
        f"Exit load: {normalize_whitespace(data.get('exit_load') or 'Not stated')}",
        f"Lock-in: {lock_in}",
        f"Minimum SIP: Rs {data.get('min_sip_investment')}",
        f"SIP allowed: {data.get('sip_allowed')}",
        f"Minimum lump sum investment: Rs {data.get('min_investment_amount')}",
        f"Minimum additional investment: Rs {data.get('mini_additional_investment')}",
        f"Minimum withdrawal: Rs {data.get('min_withdrawal')}",
        f"Launch date: {data.get('launch_date')}",
        f"ISIN: {data.get('isin')}",
        f"Face value: {data.get('face_value')}",
        f"Fund managers: {fund_managers}",
        f"Fund size (AUM): Rs {data.get('aum')} Cr",
        f"NAV: Rs {data.get('nav')} as of {data.get('nav_date')}",
        f"Stamp duty: {data.get('stamp_duty')}",
        f"Registrar: {data.get('registrar_agent')}",
        f"Source page: {source.url}",
    ]

    description = data.get("description") or data.get("meta_desc")
    if description:
        lines.extend(["", "Description:", str(description).strip()])

    # category_info is omitted: Groww serves the same contra-fund note for every
    # scheme, and its tax text is about returns.

    tax_impact = (data.get("category_info") or {}).get("tax_impact")
    if tax_impact:
        lines.extend(["", "Tax implication:", str(tax_impact).strip()])

    holdings = data.get("holdings") or []
    if holdings:
        holdings = sorted(holdings, key=lambda h: h.get("corpus_per") or 0, reverse=True)
        lines.extend(
            [
                "",
                "Portfolio holdings:",
                f"Largest holding: {holdings[0].get('company_name')}. "
                f"Total holdings: {len(holdings)}. Top holdings, largest first:",
            ]
        )
        for item in holdings[:15]:
            lines.append(
                f"{item.get('company_name')} ({item.get('sector_name')}): "
                f"{item.get('corpus_per')}% of assets"
            )

    managers = [m for m in data.get("fund_manager_details") or [] if isinstance(m, dict)]
    if managers:
        lines.extend(["", "Fund manager background:"])
        for m in managers:
            since = str(m.get("date_from") or "")[:10]
            lines.append(
                f"{m.get('person_name')} (managing since {since}). "
                f"Education: {m.get('education')} Experience: {m.get('experience')}"
            )

    amc = data.get("amc_info") or {}
    rta = data.get("rta_details") or {}
    lines.extend(
        [
            "",
            "Contact details:",
            f"Fund house phone: {amc.get('phone')}",
            f"Fund house email: {amc.get('email')}",
            f"Fund house website: {amc.get('vro_website')}",
            f"Fund house address: {amc.get('address')}",
            f"Fund house rank by total assets: {amc.get('rank')}",
            f"Registrar email: {rta.get('email')}",
            f"Registrar website: {rta.get('website')}",
            f"Registrar address: {rta.get('address')}",
        ]
    )

    # Helpful document links (public), not advice
    for label, key in (
        ("Scheme information document / SID URL", "sid_url"),
        ("Brochure link", "brochure_link"),
        ("Scheme info link", "scheme_info_link"),
    ):
        if data.get(key):
            lines.append(f"{label}: {data[key]}")

    return "\n".join(line for line in lines if line is not None)


def key_info_lines(soup: BeautifulSoup) -> list[str]:
    """Read the Key Information table as shown on the page, as "- label: value" lines."""
    lines = []
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) >= 2 and "keyInfoTable" in str(row) and cells[1]:
            label = re.sub(r"\W+", "_", cells[0]).strip("_").lower()
            lines.append(f"- {label}: {', '.join(c for c in cells[1:] if c)}")
    return lines


def format_amc_document(amc_data: Any, source: Source) -> str:
    lines = [
        f"AMC overview: {source.title}",
        f"Scheme label: {source.scheme}",
        f"Source page: {source.url}",
        "",
    ]

    blocks = amc_data if isinstance(amc_data, list) else [amc_data]
    for block in blocks:
        if not isinstance(block, dict):
            continue

        key_info = block.get("key_information")
        if isinstance(key_info, dict):
            lines.append("Key information:")
            for k, v in key_info.items():
                if v is not None and not isinstance(v, (dict, list)):
                    lines.append(f"- {k}: {v}")
            lines.append("")

        for list_key in ("content_list", "contentList", "content"):
            items = block.get(list_key)
            if isinstance(items, list):
                for item in items[:30]:
                    lines.append(_stringify_content_item(item))
                lines.append("")

        amcs = block.get("amcs")
        if isinstance(amcs, list):
            for amc in amcs[:20]:
                if isinstance(amc, dict):
                    name = amc.get("amc_name") or amc.get("name") or amc.get("fund_house")
                    aum = amc.get("aum") or amc.get("total_aum")
                    if name:
                        lines.append(f"AMC: {name}" + (f" | AUM: {aum}" if aum else ""))

        fund_categories = block.get("fund_categories")
        if isinstance(fund_categories, list):
            lines.append("Fund categories:")
            for cat in fund_categories[:40]:
                if isinstance(cat, dict):
                    lines.append(
                        f"- {cat.get('category') or cat.get('name') or cat}: "
                        f"{cat.get('fund_count') or cat.get('count') or ''}"
                    )
                else:
                    lines.append(f"- {cat}")

    text = normalize_whitespace("\n".join(lines))
    if len(text) < DEFAULT_MIN_CHARS:
        # fallback already handled by caller if still short
        return text
    return text


def _stringify_content_item(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        title = item.get("title") or item.get("heading") or item.get("name") or ""
        body = item.get("content") or item.get("description") or item.get("text") or ""
        if isinstance(body, list):
            body = " ".join(str(x) for x in body)
        return f"{title}: {body}".strip(": ").strip()
    return str(item)


def format_lock_in(lock_in: Any) -> str:
    if lock_in is None:
        return "Not stated / none"
    if isinstance(lock_in, str):
        return lock_in
    if isinstance(lock_in, dict):
        years = lock_in.get("years")
        months = lock_in.get("months")
        days = lock_in.get("days")
        if years is None and months is None and days is None:
            return "No lock-in stated"
        parts = []
        if years:
            parts.append(f"{years} year(s)")
        if months:
            parts.append(f"{months} month(s)")
        if days:
            parts.append(f"{days} day(s)")
        return ", ".join(parts) if parts else "No lock-in stated"
    return str(lock_in)


def format_fund_managers(value: Any) -> str:
    if value is None:
        return "Not stated"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        names = []
        for item in value:
            name = _manager_name(item)
            if name:
                names.append(name)
        return ", ".join(names) if names else "Not stated"
    if isinstance(value, dict):
        return _manager_name(value) or "Not stated"
    return str(value)


def _manager_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(
            item.get("person_name")
            or item.get("name")
            or item.get("fund_manager")
            or ""
        ).strip()
    return str(item).strip()


def html_to_text(soup: BeautifulSoup) -> str:
    # Work on a copy-like decomposed tree
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    for tag_name in NOISE_SELECTORS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    # Drop very repetitive short nav-like lines
    lines = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 2:
            continue
        key = line.lower()
        if key in seen and len(line) < 40:
            continue
        seen.add(key)
        lines.append(line)
    return "\n".join(lines)


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def save_cleaned(cleaned_dir: Path, doc: Document) -> tuple[Path, Path]:
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    txt_path = cleaned_dir / f"{doc.doc_id}.txt"
    meta_path = cleaned_dir / f"{doc.doc_id}.meta.json"

    txt_path.write_text(doc.text, encoding="utf-8")
    meta = asdict(doc)
    # text lives in .txt; keep meta lean but include char_count/status fields
    meta.pop("text", None)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return txt_path, meta_path


def _dig(data: dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur
