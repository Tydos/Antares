# RAG PDF

Upload PDFs and ask questions. The app extracts, chunks, and embeds your documents — then uses semantic search and an LLM to answer questions with inline citations.

## How it works

**Upload flow**
1. Browser requests a signed upload token from `/blob-upload` (HMAC-SHA256, 1-hour TTL)
2. `@vercel/blob` SDK uploads the PDF directly from the browser to Vercel Blob CDN
3. Browser calls `/upload-complete`; backend records the file and starts a background task
4. Background task: download PDF → extract text per page (pypdf) → chunk (800 chars, 100 overlap) → embed (HuggingFace, 384-dim) → store in PostgreSQL with pgvector

**Query flow**
1. Browser POSTs `{question, top_k, filenames?}` to `/query`
2. Question is embedded; pgvector cosine search (`<=>`) finds top-k chunks
3. Chunks are passed to the LLM which generates a cited answer
4. Response includes the answer, raw chunks with scores, and per-stage latency

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, `@vercel/blob` |
| Backend | FastAPI, Python 3.10 |
| Database | PostgreSQL + pgvector |
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
| POST | `/blob-upload` | Mint a signed client token for browser → Vercel Blob upload |
| POST | `/upload-complete` | Record upload and schedule background indexing |
| GET | `/documents` | List all documents with status, page count, and chunk count |
| DELETE | `/files/{filename}` | Delete a document and all its chunks |
| POST | `/query` | Semantic search + LLM answer with per-stage latency |

### Query request/response

```json
// POST /query
{ "question": "What is the refund policy?", "top_k": 5, "filenames": ["policy.pdf"] }

// Response
{
  "answer": "Refunds are issued within 30 days [policy.pdf p.4].",
  "chunks": [{ "filename": "policy.pdf", "page": 4, "score": 0.91, "content": "..." }],
  "latency": { "embed_ms": 45, "search_ms": 12, "llm_ms": 234, "total_ms": 291 }
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

## Smoke test

```bash
cd backend/tests && python test_end_to_end.py
```

Checks `/health` and `/documents` against `localhost:8000`.

## Project structure

```
backend/src/
  main.py        routes, lifespan startup, dependency injection
  config.py      pydantic settings (auto-sets route prefix on Vercel)
  database.py    postgres + pgvector — uploads table, chunks table, vector search
  pipeline.py    download → pdf.py → embedder.py → database.py (background task)
  embedder.py    HuggingFace Inference API, batch size 32
  answerer.py    HuggingFace LLM answer generation — temperature 0.2, max 400 tokens
  vercel_blob.py HMAC-SHA256 client token minting, 1-hour TTL
  pdf.py         pypdf text extraction, page-by-page generator

frontend/src/
  App.js                  layout container
  api/api.js              HTTP client for all backend routes
  components/
    UploadSection.js      file picker, progress bar, upload status
    DocumentsSection.js   document list with status badges and delete
    ChatSection.js        question input, answer card, chunk results
```

## Deployment (Vercel)

`vercel.json` routes the frontend to `/` and the API to `/_/backend/*`. `config.py` detects `VERCEL=1` and sets the route prefix automatically — no code changes needed.

## Limitations

- No OCR support — scanned or image-only PDFs are marked `skipped`
- No user authentication or access control
- Maximum 100 MB per PDF
- Chunking is character-based; very short pages may produce fewer or no chunks
