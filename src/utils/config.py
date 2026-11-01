"""Load and validate project settings from YAML + .env."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = ROOT / "config" / "settings.yaml"

REQUIRED_PATH_KEYS = ("raw", "cleaned", "chunks", "chroma", "retrieval_logs")


def project_root() -> Path:
    return ROOT


def load_settings(settings_path: Path | None = None) -> dict[str, Any]:
    """Load YAML settings, resolve paths against project root, and load .env."""
    load_dotenv(ROOT / ".env")

    path = settings_path or DEFAULT_SETTINGS_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Settings file not found: {path}")

    with path.open(encoding="utf-8") as f:
        settings = yaml.safe_load(f) or {}

    _validate(settings)
    settings["paths"] = {
        key: str((ROOT / value).resolve()) if not Path(value).is_absolute() else value
        for key, value in settings["paths"].items()
    }

    sources = settings.get("sources_file", "data/sources.csv")
    settings["sources_file"] = str(
        (ROOT / sources).resolve() if not Path(sources).is_absolute() else sources
    )
    settings["project_root"] = str(ROOT)
    settings["env"] = {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "groq"),
        "LLM_MODEL": os.getenv("LLM_MODEL", ""),
    }
    return settings


def _validate(settings: dict[str, Any]) -> None:
    if "paths" not in settings:
        raise ValueError("settings.yaml missing 'paths'")
    for key in REQUIRED_PATH_KEYS:
        if key not in settings["paths"]:
            raise ValueError(f"settings.yaml paths missing '{key}'")
    if "embedding" not in settings or "model_name" not in settings["embedding"]:
        raise ValueError("settings.yaml missing embedding.model_name")
    if "vector_db" not in settings or "provider" not in settings["vector_db"]:
        raise ValueError("settings.yaml missing vector_db.provider")
    if "chunking" not in settings:
        raise ValueError("settings.yaml missing 'chunking'")
    if "retrieval" not in settings or "top_k" not in settings["retrieval"]:
        raise ValueError("settings.yaml missing retrieval.top_k")


def ensure_directories(settings: dict[str, Any]) -> None:
    """Create artifact directories if they do not exist."""
    for key in REQUIRED_PATH_KEYS:
        Path(settings["paths"][key]).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    cfg = load_settings()
    ensure_directories(cfg)
    print("Config OK")
    print(f"  root: {cfg['project_root']}")
    print(f"  sources: {cfg['sources_file']}")
    print(f"  embedding: {cfg['embedding']['model_name']}")
    print(f"  vector_db: {cfg['vector_db']['provider']} / {cfg['vector_db']['collection']}")
    print(f"  LLM provider: {cfg['env']['LLM_PROVIDER']}")
