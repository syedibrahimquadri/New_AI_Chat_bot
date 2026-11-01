# Product Requirements Document (PRD)
## Groww Mutual Fund FAQ Assistant (RAG Demo)

| Field | Detail |
|---|---|
| **Product** | Small FAQ assistant for mutual fund scheme facts |
| **Platform context** | Groww public mutual fund pages |
| **Version** | 1.0 |
| **Status** | Draft |
| **Date** | 2026-11-01 |
| **Source** | `Doc/problemstatement.txt` |

---

## 1. Overview

Build a **facts-only FAQ assistant** that answers questions about selected HDFC Mutual Fund schemes (expense ratio, exit load, minimum SIP, ELSS lock-in, riskometer, benchmark, how to download statements) using a **RAG pipeline** over scraped official public pages.

Every answer must include **one citation link**. The product must **not** give investment advice.

This is also a **RAG learning demo**: each pipeline stage (load → chunk → embed → store → retrieve → generate) must be explicit, inspectable, and implemented phase-wise.

---

## 2. Problem Statement

Retail users and support/content teams repeatedly ask the same factual mutual fund questions. Answers should come only from official public pages, with clear citations, and without slipping into advice, performance claims, or handling of personal data.

---

## 3. Goals & Non-Goals

### Goals
- Answer factual MF scheme questions from a small, curated corpus.
- Show one clear source link per answer.
- Refuse opinionated / portfolio / buy-sell questions politely.
- Persist and expose each RAG stage’s artifacts for demo/review.
- Keep the system configurable (models, vector DB) via config / `.env`.

### Non-Goals
- Personalized portfolio advice or “should I buy/sell?” recommendations.
- Computing or comparing returns / performance rankings.
- Accepting or storing PII (PAN, Aadhaar, account numbers, OTPs, emails, phones).
- Using app back-end screenshots or third-party blogs as sources.
- Large-scale multi-AMC coverage beyond the defined scope for v1.

---

## 4. Target Users

| Persona | Need |
|---|---|
| **Retail users** | Quick factual comparison inputs (expense ratio, SIP min, exit load, etc.) |
| **Support / content teams** | Consistent, cited answers to repetitive MF FAQs |

---

## 5. Scope

### 5.1 In scope — data sources (must scrape & store)

| # | Entity | URL |
|---|---|---|
| 1 | AMC overview — HDFC Mutual Fund | https://groww.in/mutual-funds/amc/hdfc-mutual-funds |
| 2 | Large Cap — HDFC Large Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 3 | Flexi Cap — HDFC Flexi Cap Direct Plan Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| 4 | ELSS — HDFC ELSS Tax Saver Fund Direct Plan Growth | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |
| 5 | Mid Cap — HDFC Mid Cap Fund Direct Growth | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |

Additional official public URLs (Groww / AMC / SEBI / AMFI factsheets or help pages) may be added to reach **15–25 sources** for the submission source list, as long as they remain public and non-blog.

### 5.2 In scope — query types
- Expense ratio
- Exit load
- Minimum SIP
- ELSS lock-in
- Riskometer
- Benchmark
- How to download capital-gains / statements (process facts only)

### 5.3 Out of scope
- Buy/sell/hold recommendations
- Return computation or performance comparison
- Non-HDFC schemes (unless later expanded)
- Authentication, account-linked actions, or any PII workflow

---

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | System scrapes and stores content from the defined Groww public pages. | P0 |
| FR-02 | System answers factual queries using retrieved corpus context (RAG). | P0 |
| FR-03 | Every answer includes exactly one clear citation link. | P0 |
| FR-04 | Answers are ≤ 3 sentences and include `Last updated from sources: <date>`. | P0 |
| FR-05 | System refuses opinionated/portfolio questions with a polite facts-only message + relevant educational link. | P0 |
| FR-06 | UI shows welcome line, 3 example questions, and disclaimer: “Facts-only. No investment advice.” | P0 |
| FR-07 | Pipeline stages persist intermediate artifacts for demo (loaded docs, chunks, embeddings/metadata, retrieval hits). | P0 |
| FR-08 | Config file controls chunking-related and vector-DB settings so they can be changed without code rewrites. | P0 |
| FR-09 | LLM model name and API keys are loaded from `.env`. | P0 |
| FR-10 | Sample Q&A file (5–10 queries with answers + links) is produced. | P1 |
| FR-11 | Source list (CSV/MD) of 15–25 URLs used is produced. | P1 |
| FR-12 | README documents setup, scope (AMC + schemes), and known limits. | P1 |

---

## 7. Non-Functional & Compliance Constraints

| ID | Constraint |
|---|---|
| NFR-01 | **Public sources only** — no app back-end screenshots; no third-party blogs as sources. |
| NFR-02 | **No PII** — do not accept or store PAN, Aadhaar, account numbers, OTPs, emails, or phone numbers. |
| NFR-03 | **No performance claims** — if asked about returns, do not compute/compare; link to official factsheet. |
| NFR-04 | **Clarity & transparency** — short answers, explicit citations, last-updated stamp. |
| NFR-05 | Prototype must be runnable locally (or demonstrable via ≤3-min video if hosting is unavailable). |

---

## 8. UX Requirements

### Tiny UI (v1)
- Welcome line explaining the assistant
- 3 example questions (clickable or copyable)
- Chat / Q&A input
- Visible disclaimer: **“Facts-only. No investment advice.”**
- Answer area showing:
  - Short factual response (≤3 sentences)
  - One citation link
  - `Last updated from sources: <date>`

### Refusal UX
For advice-seeking prompts (e.g., “Should I buy this?”):
- Polite refusal
- Remind facts-only policy
- Provide one relevant educational / official link (not a recommendation)

---

## 9. Technical Architecture (RAG, phase-wise)

Implement and store outputs for each stage explicitly.

```
[Public Groww pages]
        │
        ▼
1. Data Loading          → raw documents / HTML→text artifacts
        │
        ▼
2. Data Chunking         → chunk files/records (strategy chosen to fit page structure)
        │
        ▼
3. Data Embedding        → vectors via sentence-transformers/all-MiniLM-L6-v2
        │
        ▼
4. Vector DB             → ChromaDB (configurable via config)
        │
        ▼
5. Data Retrieval        → same embedding model + same vector DB as ingestion
        │
        ▼
6. LLM Generation        → Groq (default), model from .env
        │
        ▼
   Cited factual answer (+ refusal path when needed)
```

### 9.1 Stage requirements

| Stage | Spec |
|---|---|
| **Data Loading** | Fetch/store content from scoped URLs; keep raw/normalized artifacts visible for demo. |
| **Data Chunking** | Coding agent chooses strategy based on page structure (e.g., section-aware or sized chunks with overlap). Strategy and parameters live in config where practical. |
| **Data Embedding** | Model: `sentence-transformers/all-MiniLM-L6-v2`. |
| **Vector DB** | Default: **ChromaDB**. Provider/path/collection names configurable. |
| **Data Retrieval** | Use the **same** embedding model and vector DB as ingestion; return top-k chunks with source metadata/URL. |
| **LLM** | Primary: **Groq** API. Model from `.env` (problem statement: `qwen/qwen3.8-27b` — verify exact Groq model id at implementation). Design config so Gemini / OpenAI / Anthropic / Mistral can be swapped later. |

### 9.2 Prompting behavior (skills under test)
- **W1 — Thinking like a model:** detect the exact fact requested; answer vs refuse.
- **W2 — LLMs & prompting:** instructional system prompt; concise phrasing; polite safe-refusals; citation wording.
- **W3 — RAGs only:** retrieve from small corpus; cite accurately (prefer AMC/SEBI/AMFI/official Groww pages).

---

## 10. Configuration & Secrets

| Item | Location | Notes |
|---|---|---|
| Vector DB type/path/collection | Config file | Default ChromaDB; changeable |
| Chunk size / overlap / strategy knobs | Config file | Tunable without code changes |
| Embedding model name | Config file | Default `all-MiniLM-L6-v2` |
| LLM provider + model | `.env` + config | Groq default; model from `.env` |
| API keys (Groq, optional others) | `.env` | Never commit secrets |

---

## 11. Deliverables

| # | Deliverable | Acceptance |
|---|---|---|
| D1 | Working prototype (app/notebook link) **or** ≤3-min demo video | Runs end-to-end Q&A with citations |
| D2 | Source list (CSV or MD) | 15–25 URLs used |
| D3 | README | Setup steps, scope (AMC + schemes), known limits |
| D4 | Sample Q&A file | 5–10 queries with assistant answers + links |
| D5 | UI disclaimer snippet | Facts-only, no advice |
| D6 | Phase artifacts | Loaded/chunked/embedded/retrieved stage outputs demonstrable |

---

## 12. Success Metrics (demo acceptance)

- ≥ 80% of sample factual questions answered correctly with a valid citation to an in-corpus source.
- 100% of advice-style questions refused without recommendations.
- No PII collected in logs or stored state.
- Each RAG stage has inspectable stored output for walkthrough.
- Answers comply with ≤3 sentences + last-updated line + one link.

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Groww page HTML changes break scraping | Prefer resilient selectors; keep raw snapshots; document refresh steps |
| Stale facts after site updates | Show “Last updated from sources”; easy re-ingest path |
| LLM hallucinates beyond retrieved context | Strict grounded prompt; answer only from retrieved chunks; refuse if insufficient |
| Wrong/missing citations | Attach source URL metadata to every chunk; require citation in output schema |
| Model id mismatch on Groq | Resolve exact model string at build time; keep in `.env` |

---

## 14. Implementation Phases (suggested)

| Phase | Outcome |
|---|---|
| **P0 — Scaffold** | Repo, config, `.env.example`, README skeleton, disclaimer copy |
| **P1 — Data Loading** | Scrape/store 5 core pages (+ expand toward 15–25 source list) |
| **P2 — Chunking** | Chosen strategy + persisted chunks |
| **P3 — Embed + ChromaDB** | Ingest with `all-MiniLM-L6-v2` |
| **P4 — Retrieval + LLM** | Groq generation with citations / refusals |
| **P5 — Tiny UI** | Welcome, examples, disclaimer, Q&A |
| **P6 — Submission pack** | Sample Q&A, source list, demo link/video, limits documented |

---

## 15. Open Questions

1. Confirm exact Groq model id for `qwen/qwen3.8-27b` (typo / naming in problem statement).
2. Confirm whether “15–25 URLs” may include SEBI/AMFI/AMC factsheet pages beyond the 5 Groww URLs.
3. Preferred prototype surface: Streamlit / Gradio / notebook / simple web app?
4. How long to retain scraped snapshots, and should re-scrape be one-click for the demo?

---

## 16. Disclaimer (required in UI)

> Facts-only. No investment advice.
>
> This assistant answers factual questions from public mutual fund pages and always shows a source link. It does not recommend buying, selling, or holding any scheme.
