"""Grade every fund and AMC fact against page data: python -m tests.run_accuracy"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

from src.generate.answer import answer_question
from src.llm.base import LLMError
from src.utils.config import load_settings

# The test shares the live app's Groq key; raise ACCURACY_DELAY to leave it headroom.
DELAY = float(os.environ.get("ACCURACY_DELAY", "4"))
# Run a slice of the 144 questions, e.g. ACCURACY_START=30 ACCURACY_COUNT=30, so one run
# never uses up the daily token quota the live app also depends on.
START = int(os.environ.get("ACCURACY_START", "0"))
COUNT = int(os.environ.get("ACCURACY_COUNT", "0")) or 10**6

TOPICS = [
    ("expense ratio", "What is the expense ratio of {n}?", lambda d, m: str(d["expense_ratio"])),
    ("exit load", "What is the exit load of {n}?", lambda d, m: _exit_token(d)),
    ("minimum SIP", "What is the minimum SIP of {n}?", lambda d, m: str(d["min_sip_investment"])),
    ("riskometer", "What is the riskometer rating of {n}?", lambda d, m: m),
    ("benchmark", "What is the benchmark of {n}?", lambda d, m: (d["benchmark"] or "").split()[0]),
    ("fund size", "What is the fund size of {n}?", lambda d, m: str(d["aum"])[:6]),
    ("top holding", "What is the largest holding of {n}?", lambda d, m: _top(d)),
    ("fund manager", "Who is the fund manager of {n}?", lambda d, m: d["fund_manager_details"][0]["person_name"].split()[-1]),
    ("launch date", "What is the launch date of {n}?", lambda d, m: d["launch_date"][-4:]),
]
AMC = [
    ("Who is the investor service officer?", "Sakseria"),
    ("Who are the trustees of HDFC Mutual Fund?", "Bhandari"),
    ("Who are the sponsors of HDFC Mutual Fund?", "Abrdn"),
    ("Who is the CEO of HDFC Mutual Fund?", "Munot"),
    ("Who is the compliance officer of HDFC Mutual Fund?", "Sapre"),
    ("Who is the CIO of HDFC Mutual Fund?", "Setalvad"),
    ("What is the total AUM of HDFC Mutual Fund?", "9,34,075"),
    ("When was HDFC Mutual Fund incorporated?", "1999"),
    ("What is the address of HDFC Mutual Fund?", "Churchgate"),
]


def _exit_token(d: dict) -> str:
    text = (d["exit_load"] or "").strip()
    return "nil" if text.lower() == "nil" else (re.search(r"[\d.]+%", text) or [text[:8]])[0]


def _top(d: dict) -> str:
    top = max(d["holdings"], key=lambda h: h["corpus_per"] or 0)
    return top["company_name"].split()[0]


def ask(question: str, settings: dict) -> str:
    for _ in range(6):
        try:
            return answer_question(question, settings).text
        except LLMError as exc:
            if "429" not in str(exc) and "rate" not in str(exc).lower():
                raise
            if "tokens per day" in str(exc.__cause__):
                # Waiting will not help, and retrying keeps eating what the live app has left.
                raise SystemExit("Daily token limit reached; stopping. Resume this batch tomorrow.")
            time.sleep(30)
    raise SystemExit("Rate limit did not clear.")


def main() -> int:
    settings = load_settings()
    raw = Path(settings["paths"]["raw"])
    cleaned = Path(settings["paths"]["cleaned"])
    failures, total, index = [], 0, -1

    def grade(question: str, expected: str) -> None:
        nonlocal total, index
        index += 1
        if not START <= index < START + COUNT:
            return
        total += 1
        got = ask(question, settings)
        if expected.lower().replace(",", "") not in got.lower().replace(",", ""):
            failures.append((question, expected, got))
            print(f"FAIL {question}\n     want {expected!r}, got: {got[:150]}", flush=True)
        time.sleep(DELAY)

    for question, expected in AMC:
        grade(question, expected)
    for meta_path in sorted(cleaned.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text("utf-8"))
        if not meta["scheme"].startswith("HDFC ") or meta["scheme"] == "HDFC MF":
            continue
        soup = BeautifulSoup((raw / f"{meta['doc_id']}.html").read_bytes(), "lxml")
        data = json.loads(soup.find("script", id="__NEXT_DATA__").string)
        d = data["props"]["pageProps"]["mfServerSideData"]
        risk = re.search(r"Risk is (.+?)\s*$", d["meta_desc"]).group(1)
        for _, template, expected in TOPICS:
            grade(template.format(n=meta["title"]), expected(d, risk))

    print(f"\n{total - len(failures)}/{total} correct")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
