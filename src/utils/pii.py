"""PII detection. Questions that match are rejected before anything is stored."""

from __future__ import annotations

import re

_PII_PATTERNS = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)")),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)),
    ("aadhaar", re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    ("account_number", re.compile(r"(?<!\d)\d{9,18}(?!\d)")),
    ("otp", re.compile(r"\botp\b\D{0,12}\d{4,8}\b", re.IGNORECASE)),
]


def contains_pii(text: str) -> bool:
    """Return True if the text appears to contain PII."""
    return find_pii_types(text) != []


def find_pii_types(text: str) -> list[str]:
    """Return list of matched PII type labels."""
    return [label for label, pattern in _PII_PATTERNS if pattern.search(text)]
