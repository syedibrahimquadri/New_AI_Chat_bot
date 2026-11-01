"""Rule-based intent checks that run before retrieval or any LLM call."""

from __future__ import annotations

import re

from src.utils.pii import find_pii_types

EDUCATION_URL = "https://investor.sebi.gov.in/securities-mf-investments.html"
AMC_URL = "https://groww.in/mutual-funds/amc/hdfc-mutual-funds"

_ADVICE = re.compile(
    r"\b(should i|shall i|can i buy|is it (good|safe|worth)|worth (buying|investing)|"
    r"recommend|suggest|advice|advise|best|better|good (fund|time|investment)|"
    r"which (fund|scheme|one)\b.*\b(for me|choose|pick|invest)|"
    r"buy|sell|hold on to|switch to|redeem now|my portfolio)\b",
    re.I,
)
_PREDICTION = re.compile(
    r"\b(predict\w*|forecast\w*|tomorrow|next (week|month|year)|will .* (rise|fall|go up|go down))\b",
    re.I,
)
_PERFORMANCE = re.compile(
    r"\b(returns?|performance|performed|cagr|xirr|gains? (of|from|in)|outperform\w*|"
    r"how much (will|would|can) i (get|earn|make))\b",
    re.I,
)
# "capital gains" and "statement" questions are process facts, not performance.
_PROCESS = re.compile(r"\b(capital[- ]gains?|statement|cas)\b", re.I)
_OTHER_AMC = re.compile(
    r"\b(sbi|icici|axis|nippon|kotak|uti|tata|aditya birla|dsp|mirae|parag parikh|ppfas|"
    r"quant|motilal|franklin|canara|edelweiss|groww (fund|nifty|elss))\b",
    re.I,
)
_NEEDS_SCHEME = re.compile(
    r"\b(expense ratio|ter|exit load|minimum sip|min(imum)? (sip|investment|lumpsum)|sip amount|"
    r"lock-?in|riskometer|risk (rating|level)|benchmark|fund manager|nav|fund size|holdings?|stamp duty)\b",
    re.I,
)

MESSAGES = {
    "pii": (
        "Please do not share personal details such as PAN, Aadhaar, account numbers, OTPs, "
        "emails or phone numbers. Your message was not stored; please ask again without them."
    ),
    "advice": (
        "I can only share facts about mutual fund schemes, not investment advice or "
        "recommendations. This official investor education page can help you learn more."
    ),
    "prediction": (
        "I cannot predict NAVs or future market movements because I only share published "
        "facts. This official investor education page can help you learn more."
    ),
    "performance": (
        "I do not calculate or compare returns. Please check the official source page below "
        "for published performance information."
    ),
    "out_of_scope": (
        "That scheme is not in my sources, which cover selected HDFC Mutual Fund schemes only."
    ),
    "needs_scheme": (
        "Please name the HDFC scheme you mean, for example HDFC Mid Cap Fund Direct Growth."
    ),
}


def classify(question: str, schemes_named: list[str]) -> str:
    """Return pii, advice, prediction, performance, out_of_scope, needs_scheme or factual."""
    if find_pii_types(question):
        return "pii"
    is_process = bool(_PROCESS.search(question))
    if _PREDICTION.search(question):
        return "prediction"
    if _ADVICE.search(question):
        return "advice"
    if _PERFORMANCE.search(question) and not is_process:
        return "performance"
    if _OTHER_AMC.search(question):
        return "out_of_scope"
    if _NEEDS_SCHEME.search(question) and not schemes_named:
        return "needs_scheme"
    return "factual"
