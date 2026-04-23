# Not ChatGPT

Upload PDFs and ask questions with persistent chat memory. The app extracts, chunks, and embeds your documents — then uses hybrid search (semantic + keyword, fused with Reciprocal Rank Fusion) and an LLM to answer questions with inline citations. Conversation history is stored in PostgreSQL and restored on page load.

## How it works

**Upload flow**
1. Browser requests a signed upload token from `/request_upload_token` (HMAC-SHA256, 1-hour TTL)
2. `@vercel/blob` SDK uploads the PDF directly from the browser to Vercel Blob CDN
3. Browser calls `/upload-complete`; backend records the file and starts a background task
4. Background task: download PDF → extract text per page (pypdf) → chunk (800 chars, 100 overlap) → embed (HuggingFace, 384-dim) → store in PostgreSQL with pgvector + tsvector

**Chat flow (persistent)**
1. Browser POSTs `{question, search_mode?}` to `/chat`
2. Backend loads full conversation history from the `messages` table
3. Embeds question → searches chunks → LLM generates answer with history context (last 6 turns)
4. Both turns saved to `messages`; response includes answer, chunks, and latency
5. On page load, `GET /history` restores the full thread

**Search modes**
- **hybrid** (default): pgvector cosine search + PostgreSQL `ts_rank`, fused with Reciprocal Rank Fusion (RRF, k=60)
- **semantic**: pgvector cosine search only
- **keyword**: full-text search only, OR-joined `to_tsquery`

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, `@vercel/blob` |
| Backend | FastAPI, Python 3.10 |
| Database | PostgreSQL + pgvector + tsvector (GIN index) |
| Search | Hybrid RRF — pgvector cosine + `ts_rank` full-text |
| Embeddings | HuggingFace Inference API — `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| LLM | HuggingFace Inference API — `meta-llama/Llama-3.2-1B-Instruct` |
| Storage | Vercel Blob |
| Infra | Docker Compose (local), Vercel (prod) |

## Quick start

```bash
cp .env.example .env        # fill in the variables (see below)
docker compose up --build   # FastAPI on :8000, React on :3000
```

Swagger UI: http://localhost:8000/docs

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `BLOB_READ_WRITE_TOKEN` | Yes | — | Vercel Blob token for minting signed client upload tokens |
| `HF_TOKEN` | No | — | HuggingFace API key (embeddings + LLM) |
| `HF_EMBED_MODEL` | No | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `HF_LLM_MODEL` | No | `meta-llama/Llama-3.2-1B-Instruct` | LLM for answer generation |

Without `HF_TOKEN`, embedding and answer generation will fail. Without `BLOB_READ_WRITE_TOKEN`, uploads will fail. The app still starts and serves `/health`.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + DB connectivity status |
| POST | `/request_upload_token` | Mint a signed client token for browser → Vercel Blob upload |
| POST | `/upload-complete` | Record upload and schedule background indexing |
| GET | `/documents` | List all documents with status, page count, and chunk count |
| DELETE | `/files/{filename}` | Delete a document and all its chunks |
| POST | `/chat` | Persistent chat — search + LLM with conversation history |
| GET | `/history` | Return full conversation history |
| POST | `/query` | Stateless search + LLM (no history saved, kept for compatibility) |

### Chat request/response

```json
// POST /chat
{
  "question": "What is the refund policy?",
  "top_k": 5,
  "search_mode": "hybrid"
}

// Response
{
  "answer": "Refunds are issued within 30 days [policy.pdf p.4].",
  "chunks": [{ "filename": "policy.pdf", "page": 4, "score": 0.0161, "content": "..." }],
  "latency": { "embed": 45, "search": 12, "llm": 234, "total": 291 }
}
```

`top_k` is clamped to [1, 20]. `filenames` is optional; omit to search across all documents.

## Document statuses

| Status | Meaning |
|---|---|
| `pending` | Upload received; indexing in progress |
| `indexed` | Text extracted, chunked, and embedded successfully |
| `skipped` | PDF contained no extractable text (scanned/image-only) |
| `failed` | Indexing error (check logs) |

## Tests

```bash
docker compose exec fastapi python -m pytest tests/test_api.py tests/test_database.py -v
```

- **`test_api.py`** (15 tests) — FastAPI TestClient with mocked dependencies; no live services needed. Covers health, documents, history, `/query`, `/chat`, error paths.
- **`test_database.py`** (10 tests) — Integration tests against a live database. Covers messages CRUD, upload CRUD, status updates, and error cases.

### Search mode evaluation

Run `backend/tests/evaluate.py` against a QA JSON file to benchmark retrieval quality across all three search modes:

```bash
python backend/tests/evaluate.py --qa backend/tests/input/qa_pairs.json --top-k 5 --out backend/tests/results.json
```

Results on a 20-question resume QA set (top-k=5):

| Mode | Precision@5 | Recall@5 | F1 |
|---|---|---|---|
| hybrid | 40.0% | 100.0% (20/20) | 57.1% |
| semantic | 13.0% | 40.0% (8/20) | 19.6% |
| keyword | 0.0% | 0.0% (0/20) | 0.0% |

Hybrid search finds a relevant chunk for every question; semantic alone misses 60% of questions on entity-heavy resume content.

## Project structure

```
backend/
  src/
    main.py              routes, lifespan startup, dependency injection
    config.py            pydantic settings (auto-sets route prefix on Vercel)
    schemas.py           Pydantic request/response models
    interfaces.py        Protocol definitions — Database, Embedder, Extractor, Generator

    ingestion/
      service.py         IngestionService — download → parse → embed → store
      pdf_parser.py      pypdf extraction, 800-char chunks / 100-char overlap
      upload_token.py    HMAC-SHA256 client token minting (1-hour TTL)

    inference/
      embedding.py       HuggingFace embedding service (384-dim, batched)
      generator.py       HuggingFace LLM — history-aware answer generation

    storage/
      database.py        PostgreSQL — uploads, chunks (pgvector + tsvector), messages

    utils/
      latency.py         LatencyTracker helper

  tests/
    test_api.py          API tests (mocked)
    test_database.py     DB integration tests

frontend/src/
  App.js                 two-column layout — sidebar + chat panel
  api/api.js             HTTP client for all backend routes
  components/
    UploadSection.js     "+ Upload Document" button, progress bar
    DocumentsSection.js  knowledge base file list with hover-delete
    ChatSection.js       persistent chat thread, search mode toggle, send button
    DevPanel.js          always-on right panel — session stats, latency bars, chunk inspector
```

## Deployment (Vercel)

`vercel.json` routes the frontend to `/` and the API to `/_/backend/*` using vercel.json


## Limitations

- No OCR support — scanned or image-only PDFs are marked `skipped`
- No user authentication — conversation history is global (single shared thread)
- Maximum 100 MB per PDF
- Chunking is character-based; very short pages may produce fewer or no chunks
- LLM context is capped at the last 6 conversation turns to stay within token limits
- Ingestion pipeline is still not asnyc