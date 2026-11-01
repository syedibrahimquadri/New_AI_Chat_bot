# Groww Mutual Fund FAQ Assistant (RAG Demo)

Facts-only FAQ assistant for selected HDFC Mutual Fund schemes using a phase-wise RAG pipeline over public Groww pages.

> **Facts-only. No investment advice.**

## Scope

- AMC: HDFC Mutual Fund
- Schemes: 15 Direct Growth plans, including Large Cap, Flexi Cap, ELSS Tax Saver and Mid Cap (full list in `data/sources.csv`)
- Answers factual queries (expense ratio, exit load, min SIP, lock-in, riskometer, benchmark, statement download how-to)
- Every answer includes one source link

## Setup

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
copy .env.example .env
# Edit .env and set GROQ_API_KEY (and LLM_MODEL if needed)
```

Verify config:

```bash
python -m src.utils.config
```

## Run

```bash
python -m src.ingest.pipeline --stage all     # or scrape | load | chunk | embed | store
streamlit run src/ui/app.py
python -m src.generate.answer --q "What is the exit load of HDFC Flexi Cap?"
python -m tests.run_guardrails                # add --write-samples to save samples/sample_qa.md
```

`--write-samples` and live answers need a real `GROQ_API_KEY`. Without a key, the guardrail run uses a stand-in LLM. To refresh facts, run the `all` stage again.

## Project layout

See `Doc/implementation.md` for the phase-wise plan. Artifacts land in `data/raw`, `data/cleaned`, `data/chunks`, and `chroma/`.

## Known limits

- Small corpus: 18 public pages in `data/sources.csv`, HDFC schemes on Groww plus two SEBI investor pages
- No buy/sell advice, no return calculations, no PII handling
- Facts come from data embedded in Groww pages, so a Groww page change may require a loader update
- hdfcfund.com blocks automated requests, so AMC documents are not in the corpus
- Statement questions rely on SEBI's general CAS page; there are no step-by-step capital-gains download instructions
- Guardrails are rule-based and can occasionally refuse a harmless question that uses a word like "buy"
- Only Groq is implemented; other LLM providers would need a client in `src/llm/`

## Docs

- `Doc/problemstatement.txt`
- `Doc/PRD.md`
- `Doc/architecture.md`
- `Doc/implementation.md`

## Answers and app

- Facts covered: expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, fund size, NAV, top holdings, fund manager, launch date and HDFC Mutual Fund details. Return figures are excluded on purpose.
- The app is a single chat window with follow-ups for the fund being discussed. If the main Groq model is rate-limited, backup models take over.

## Tests

```bash
python -m tests.run_guardrails   # refusals, citations and format
python -m tests.run_accuracy     # 144 fact questions; about 15 minutes and uses Groq quota
```

Scraped data and the vector index are not committed. Run the pipeline after cloning.

## Vercel deployment

The chat page in `web/` is hosted on Vercel, and it sends `/api/*` requests to the Python API in `backend/`, hosted on Render (`render.yaml`).

- Vercel: import the repo and set Root Directory to `web`.
- Render: create a Blueprint from the repo and set `GROQ_API_KEY`.
- If the Render URL is not `https://fundfacts-api.onrender.com`, update `web/vercel.json`.

Run locally with `uvicorn backend.main:app --port 8000`, then open http://localhost:8000.
