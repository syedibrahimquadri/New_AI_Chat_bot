"""CLI for phase-wise ingest pipeline."""

from __future__ import annotations

import argparse
import logging
import sys

from src.ingest.load import run_load
from src.ingest.scrape import run_scrape
from src.utils.config import load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MF FAQ RAG ingest pipeline")
    parser.add_argument(
        "--stage",
        required=True,
        choices=["scrape", "load", "chunk", "embed", "store", "all"],
        help="Pipeline stage to run",
    )
    return parser


def _run_index_stages(stages: tuple[str, ...], settings: dict) -> None:
    """Imported lazily so scrape/load do not need the embedding libraries."""
    for stage in stages:
        if stage == "chunk":
            from src.ingest.chunk import chunk

            chunk(settings)
        elif stage == "embed":
            from src.ingest.embed import embed

            embed(settings)
        else:
            from src.ingest.embed import store

            store(settings)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()

    if args.stage == "scrape":
        report = run_scrape(settings)
        print(report.summary())
        return 0 if report.failure_count == 0 else 1

    if args.stage == "load":
        report = run_load(settings)
        print(report.summary())
        return 0 if report.failure_count == 0 else 1

    if args.stage == "all":
        scrape_report = run_scrape(settings)
        print(scrape_report.summary())
        if scrape_report.failure_count:
            return 1
        load_report = run_load(settings)
        print(load_report.summary())
        if load_report.failure_count:
            return 1
        _run_index_stages(("chunk", "embed", "store"), settings)
        return 0

    _run_index_stages((args.stage,), settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
