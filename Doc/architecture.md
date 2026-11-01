# Architecture
## Groww Mutual Fund FAQ Assistant (RAG Demo)

| Field | Detail |
|---|---|
| **Product** | Facts-only mutual fund FAQ assistant |
| **Based on** | `Doc/PRD.md` v1.0 |
| **Version** | 1.0 |
| **Date** | 2026-11-01 |

---

## 1. Purpose

Describe the technical architecture for a small, phase-wise **RAG** system that:

1. Ingests official public Groww / MF pages for a fixed HDFC corpus
2. Stores **inspectable artifacts at every pipeline stage** (demo requirement)
3. Answers factual queries with **one citation link**
4. Refuses advice / performance / PII-related requests

---

## 2. Design Principles

| Principle | Implication |
|---|---|
| **Stage-explicit RAG** | Load → chunk → embed → store → retrieve → generate each write durable artifacts |
| **Grounded answers only** | LLM may use retrieved chunks only; otherwise refuse |
| **Config over code** | Chunking, embedding model, vector DB, top-k live in config |
| **Secrets out of repo** | API keys + LLM model id in `.env` |
| **Facts-only compliance** | Prompt + guardrails enforce no advice, no PII, no return math |
| **Swappable providers** | ChromaDB default; LLM interface allows Groq now, others later |

---

## 3. High-Level System Context

```text
┌──────────────────┐     scrape (public HTTP)     ┌─────────────────────────┐
│  Groww / official│ ◄─────────────────────────── │  Ingestion Worker       │
│  public pages    │                              │  (load → chunk → embed) │
└──────────────────┘                              └───────────┬─────────────┘
                                                              │
                                                              ▼
                                                    ┌─────────────────────┐
                                                    │  Artifact Store     │
                                                    │  raw / chunks /     │
                                                    │  meta + ChromaDB    │
                                                    └──────────┬──────────┘
                                                               │
┌──────────────────┐   question    ┌────────────────┐         │
│  Tiny UI         │ ────────────► │  Query Service │ ◄───────┘
│  (Streamlit or   │ ◄──────────── │  retrieve+LLM  │
│   Gradio / web)  │   answer+cite └────────────────┘
└──────────────────┘                      │
                                          ▼
                                 ┌─────────────────┐
                                 │  Groq LLM API   │
                                 │  (model via .env)│
                                 └─────────────────┘
```

**Actors**
- Retail user / support user → Tiny UI
- Builder / demo presenter → inspects stage folders + ChromaDB
- External: Groww public pages, Groq API

---

## 4. Logical Components

| Component | Responsibility |
|---|---|
| **Source Registry** | Canonical list of allowed URLs (5 core + up to 15–25 total); drives scrape + citations |
| **Loader** | Fetch HTML, normalize to text/markdown, save raw + clean docs with metadata |
| **Chunker** | Split docs using configured strategy; persist chunks with `source_url`, `scheme`, `section` |
| **Embedder** | Encode chunks with `sentence-transformers/all-MiniLM-L6-v2` |
| **Vector Store Adapter** | Upsert/query ChromaDB (interface allows future swap) |
| **Retriever** | Embed query with same model; return top-k chunks + metadata |
| **Guardrails** | Classify intent: factual / advice / performance / PII / out-of-scope |
| **Generator** | Build grounded prompt; call Groq; enforce ≤3 sentences, 1 link, last-updated |
| **Tiny UI** | Welcome, 3 examples, disclaimer, Q&A, show citation + timestamp |
| **Config & Secrets** | `config.yaml` (or similar) + `.env` |

---

## 5. Proposed Repository Layout

```text
New_AI_Chat_bot/
├── Doc/
│   ├── problemstatement.txt
│   ├── PRD.md
│   └── architecture.md
├── config/
│   └── settings.yaml          # chunking, embed model, chroma, top_k, paths
├── .env.example               # GROQ_API_KEY, LLM_MODEL, ...
├── data/
│   ├── sources.csv            # 15–25 URL registry (deliverable)
│   ├── raw/                   # stage 1: fetched HTML / snapshots
│   ├── cleaned/               # stage 1: normalized text
│   ├── chunks/                # stage 2: chunk JSON/JSONL
│   └── retrieval_logs/        # optional demo: per-query hits
├── chroma/                    # stage 3–4: persistent ChromaDB dir
├── src/
│   ├── ingest/
│   │   ├── load.py
│   │   ├── chunk.py
│   │   ├── embed.py
│   │   └── pipeline.py
│   ├── retrieve/
│   │   └── retriever.py
│   ├── generate/
│   │   ├── prompts.py
│   │   ├── guardrails.py
│   │   └── answer.py
│   ├── llm/
│   │   ├── base.py
│   │   └── groq_client.py     # (+ stubs for gemini/openai/anthropic/mistral)
│   ├── ui/
│   │   └── app.py
│   └── utils/
│       ├── config.py
│       └── pii.py
├── samples/
│   └── sample_qa.md           # 5–10 Q&A deliverable
├── README.md
└── requirements.txt
```

Stage folders under `data/` exist so each RAG phase is **demo-visible** without opening the vector DB.

---

## 6. End-to-End Data Flows

### 6.1 Ingestion (batch / CLI)

```text
sources.csv
    → Loader.fetch(url)
    → save data/raw/{id}.html
    → normalize → data/cleaned/{id}.txt (+ metadata.json)
    → Chunker.split(doc, strategy from config)
    → save data/chunks/{id}.jsonl
    → Embedder.encode(chunks)
    → VectorStore.upsert(ids, vectors, documents, metadatas)
    → chroma/ collection ready
```

**Chunk metadata (minimum)**

| Field | Purpose |
|---|---|
| `source_url` | Citation link (mandatory) |
| `title` / `scheme` | Display + filtering |
| `doc_id` / `chunk_id` | Traceability |
| `section` | Optional section heading |
| `scraped_at` | Feeds “Last updated from sources” |

### 6.2 Query (online)

```text
User question
    → PII scrub / reject if PII present
    → Guardrails.intent(question)
         ├─ advice | performance | out-of-scope → refusal template + educational link
         └─ factual → continue
    → Retriever.embed(question)   # same MiniLM model
    → ChromaDB.query(top_k)
    → save retrieval_logs/{timestamp}.json   # demo artifact
    → Generator(prompt = system + chunks + question)
    → Groq completion
    → Post-validate: ≤3 sentences, exactly one URL, last-updated line
    → UI renders answer
```

---

## 7. RAG Stage Architecture (demo contract)

| Stage | Input | Output artifact | Tech |
|---|---|---|---|
| **1. Data Loading** | URL list | `data/raw/*`, `data/cleaned/*` | `httpx`/`requests` + HTML→text (e.g. BeautifulSoup) |
| **2. Data Chunking** | Cleaned docs | `data/chunks/*.jsonl` | Strategy from config (see §8) |
| **3. Data Embedding** | Chunk texts | Vectors in memory → upsert | `sentence-transformers/all-MiniLM-L6-v2` |
| **4. Vector DB** | Embeddings + metadata | `chroma/` persistent collection | ChromaDB |
| **5. Data Retrieval** | User query | Top-k chunks + `retrieval_logs/` | Same embedder + Chroma |
| **6. LLM Generation** | Query + chunks | Cited answer or refusal | Groq API |

---

## 8. Chunking Strategy

PRD allows the implementation to choose based on page shape. Default recommendation:

| Setting | Default | Rationale |
|---|---|---|
| Strategy | **Section-aware recursive** (headings → paragraphs → size split) | MF pages are sectioned (expense ratio, exit load, SIP, etc.) |
| `chunk_size` | 500–800 tokens (or ~1200–2000 chars) | Fits fact blocks without huge context |
| `chunk_overlap` | 10–15% | Preserve boundary facts |
| Fallback | Fixed-size splitter if sections missing | Robust to HTML variance |

All knobs live in `config/settings.yaml` so they can change without code edits.

---

## 9. Retrieval & Generation Design

### 9.1 Retrieval
- Embedding model: **identical** to ingestion (`all-MiniLM-L6-v2`)
- Similarity: cosine (Chroma default)
- `top_k`: configurable (suggest 3–5 for small corpus)
- Optional metadata filter by `scheme` if user names a fund

### 9.2 Guardrails (pre-LLM)

| Intent | Behavior |
|---|---|
| Factual (expense ratio, SIP, exit load, lock-in, riskometer, benchmark, statement download how-to) | Retrieve + answer |
| Advice (“should I buy/sell/hold?”) | Refuse + educational link |
| Performance / returns compare | Refuse compute; link factsheet URL if in corpus |
| PII present | Reject; do not store; warn user |
| Unrelated / insufficient context | Refuse or “not in sources” with nearest educational link |

### 9.3 Generation contract
- System prompt encodes: facts-only, ≤3 sentences, one citation URL from provided chunks only, append `Last updated from sources: <date>`, no advice
- Temperature low (e.g. 0–0.2) for determinism
- If top chunks lack the fact → do not invent; say data not found in sources

### 9.4 Answer schema (logical)

```json
{
  "type": "answer | refusal",
  "text": "… ≤3 sentences …",
  "citation_url": "https://…",
  "last_updated_from_sources": "YYYY-MM-DD",
  "retrieved_chunk_ids": ["…"]
}
```

---

## 10. LLM Provider Abstraction

```text
LLMClient (interface)
    ├── GroqClient          ← default (P0)
    ├── GeminiClient        ← stub / later
    ├── OpenAIClient        ← stub / later
    ├── AnthropicClient     ← stub / later
    └── MistralClient       ← stub / later
```

| Config / env | Example |
|---|---|
| `LLM_PROVIDER` | `groq` |
| `LLM_MODEL` | from `.env` (verify Groq id for Qwen model named in PRD) |
| `GROQ_API_KEY` | secret |

---

## 11. Configuration Model

### `config/settings.yaml` (non-secret)

```yaml
sources_file: data/sources.csv
paths:
  raw: data/raw
  cleaned: data/cleaned
  chunks: data/chunks
  chroma: chroma
  retrieval_logs: data/retrieval_logs

chunking:
  strategy: section_recursive
  chunk_size: 1500
  chunk_overlap: 200

embedding:
  model_name: sentence-transformers/all-MiniLM-L6-v2

vector_db:
  provider: chromadb          # changeable per PRD
  collection: mf_faq
  distance: cosine

retrieval:
  top_k: 4

generation:
  max_sentences: 3
  require_citation: true
```

### `.env` (secret / environment-specific)

```text
GROQ_API_KEY=
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
```

---

## 12. UI Architecture

**v1 surface (recommended):** Streamlit or Gradio single page — fastest for demo.

| UI element | Maps to PRD |
|---|---|
| Welcome line | Product intro |
| 3 example questions | Onboarding |
| Disclaimer banner | “Facts-only. No investment advice.” |
| Input box | User query (reject/strip PII patterns) |
| Answer panel | Text + citation link + last-updated |
| Optional “Show retrieval” expander | Demo of stage 5 hits |

No auth, no accounts, no file uploads of personal documents.

---

## 13. Security, Privacy & Compliance

| Control | Implementation |
|---|---|
| Public sources only | Scrape allowlist from `sources.csv`; block non-listed domains |
| No PII storage | Regex/heuristic detector on input; drop matches; never log raw PII |
| No advice | Guardrails + system prompt + refusal templates |
| No performance math | Guardrails short-circuit returns questions |
| Secrets | `.env` + `.gitignore`; ship `.env.example` only |
| Provenance | Every chunk carries `source_url` + `scraped_at` |

---

## 14. Error Handling

| Failure | Behavior |
|---|---|
| Scrape 4xx/5xx / HTML change | Keep last good snapshot; log failure; README refresh steps |
| Empty retrieval | Refusal / “not found in sources” |
| LLM timeout / API error | User-visible retry message; no fabricated answer |
| Missing API key | Fail fast at startup with clear README hint |
| Config invalid | Validate on boot; refuse to ingest/serve |

---

## 15. Deployment & Runtime

| Mode | Use |
|---|---|
| **Local prototype** | `python -m src.ingest.pipeline` then `streamlit run src/ui/app.py` |
| **Notebook** | Optional alternate deliverable for walkthrough |
| **Hosted** | Optional; if unavailable, ≤3-min demo video per PRD |

**Runtime dependencies (indicative):** Python 3.10+, `sentence-transformers`, `chromadb`, `groq`, HTTP + HTML parsing libs, UI framework.

No mandatory cloud DB — Chroma persistence on disk is enough for the demo corpus size.

---

## 16. Observability for Demo

To satisfy “each stage data stored explicitly”:

1. Browse `data/raw` → `cleaned` → `chunks`
2. Open Chroma collection count / sample metadatas
3. Toggle UI expander for retrieval hits
4. Show final answer with citation + last-updated

Optional: simple CLI `make demo-stages` that prints counts per folder.

---

## 17. Mapping to PRD Requirements

| PRD ID | Architecture support |
|---|---|
| FR-01 | Loader + source registry |
| FR-02 | Retriever + Generator |
| FR-03 / FR-04 | Answer schema + post-validate |
| FR-05 | Guardrails refusal path |
| FR-06 | Tiny UI component |
| FR-07 | `data/*` + `retrieval_logs/` + chroma |
| FR-08 / FR-09 | `settings.yaml` + `.env` |
| NFR-01–04 | Allowlist, PII filter, prompts, citations |
| W1–W3 | Intent detect, prompting, grounded RAG |

---

## 18. Build Sequence (aligned with PRD phases)

1. Scaffold repo, config, `.env.example`
2. Implement Loader → persist raw/cleaned
3. Implement Chunker → persist chunks
4. Embed + Chroma upsert
5. Retriever + Groq generator + guardrails
6. Tiny UI + disclaimer
7. Package deliverables (sources list, sample Q&A, README, demo)

---

## 19. Open Architecture Decisions

| Decision | Options | Tentative |
|---|---|---|
| UI framework | Streamlit / Gradio / notebook | Streamlit |
| HTML extraction | BeautifulSoup vs readability-style | BeautifulSoup + scheme-specific field hooks if needed |
| Exact Groq model id | As named in PRD vs current Groq catalog | Confirm at implementation |
| Extra URLs beyond 5 | SEBI/AMFI/AMC factsheets / Groww help | Yes, to reach 15–25, allowlisted only |
