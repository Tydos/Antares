# RAG PDF

Upload PDFs and ask questions. The app extracts, chunks, and embeds your documents — then uses hybrid search (semantic + keyword, fused with Reciprocal Rank Fusion) and an LLM to answer questions with inline citations.

## How it works

**Upload flow**
1. Browser requests a signed upload token from `/request_upload_token` (HMAC-SHA256, 1-hour TTL)
2. `@vercel/blob` SDK uploads the PDF directly from the browser to Vercel Blob CDN
3. Browser calls `/upload-complete`; backend records the file and starts a background task
4. Background task: download PDF → extract text per page (pypdf) → chunk (800 chars, 100 overlap) → embed (HuggingFace, 384-dim) → store in PostgreSQL with pgvector + tsvector

**Query flow**
1. Browser POSTs `{question, top_k, filenames?, search_mode?}` to `/query`
2. Depending on `search_mode`:
   - **hybrid** (default): pgvector cosine search + PostgreSQL full-text search (`ts_rank`), fused with Reciprocal Rank Fusion (RRF, k=60)
   - **semantic**: pgvector cosine search only
   - **keyword**: full-text search only, OR-joined `to_tsquery`
3. Top-k chunks are passed to the LLM which generates a cited answer
4. Response includes the answer, raw chunks with scores, and per-stage latency

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
| POST | `/query` | Hybrid/semantic/keyword search + LLM answer with per-stage latency |

### Query request/response

```json
// POST /query
{
  "question": "What is the refund policy?",
  "top_k": 5,
  "filenames": ["policy.pdf"],
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

`search_mode` options:

| Value | Mechanism | Best for |
|---|---|---|
| `hybrid` (default) | RRF fusion of vector + full-text | General use — catches semantic and exact-keyword hits |
| `semantic` | pgvector cosine similarity | Conceptual questions, paraphrases |
| `keyword` | PostgreSQL `ts_rank` (OR tokens) | Exact terms, names, codes, acronyms |

## Document statuses

| Status | Meaning |
|---|---|
| `pending` | Upload received; indexing in progress |
| `indexed` | Text extracted, chunked, and embedded successfully |
| `skipped` | PDF contained no extractable text (scanned/image-only) |
| `failed` | Indexing error (check logs) |

## Smoke test

```bash
cd backend/tests && python test_end_to_end.py
```

Checks `/health` and `/documents` against `localhost:8000`.

## Project structure

```
backend/src/
  main.py             routes, lifespan startup, dependency injection
  config.py           pydantic settings (auto-sets route prefix on Vercel)
  database.py         postgres + pgvector + tsvector — uploads, chunks, hybrid search
  ingestion_service.py download → pdf_parser.py → embedding.py → database.py
  embedding.py        HuggingFace Inference API, batch size 32
  generator.py        HuggingFace LLM answer generation — temperature 0.2, max 400 tokens
  create_upload_token.py HMAC-SHA256 client token minting, 1-hour TTL
  pdf_parser.py       pypdf text extraction, 800-char chunks / 100-char overlap
  interfaces.py       Protocol definitions for Database, Embedder, Extractor, Generator
  schemas.py          Pydantic request/response models
  utils.py            LatencyTracker helper

frontend/src/
  App.js                  layout container
  api/api.js              HTTP client for all backend routes
  components/
    UploadSection.js      file picker, progress bar, upload status
    DocumentsSection.js   document list with status badges and delete
    ChatSection.js        question input, search mode toggle, answer card, chunk results
```

## Deployment (Vercel)

`vercel.json` routes the frontend to `/` and the API to `/_/backend/*`. `config.py` detects `VERCEL=1` and sets the route prefix automatically — no code changes needed.

## Limitations

- No OCR support — scanned or image-only PDFs are marked `skipped`
- No user authentication or access control
- Maximum 100 MB per PDF
- Chunking is character-based; very short pages may produce fewer or no chunks
