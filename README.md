# RAG PDF

Upload PDFs, ask questions, get AI-generated answers backed by your documents.

## What it does

1. **Upload** a PDF → stored in Vercel Blob; text is extracted, chunked, and embedded into PostgreSQL (pgvector)
2. **Query** → semantic search finds the most relevant chunks; Google Gemini generates a cited answer
3. Scanned/image-only PDFs are marked `skipped` (no OCR)

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18, `@vercel/blob` |
| Backend | FastAPI, Python 3.10 |
| Database | PostgreSQL + pgvector |
| Embeddings | HuggingFace Inference API (`sentence-transformers/all-MiniLM-L6-v2`, 384-dim) |
| LLM | Google Gemini (`gemini-2.5-flash`) |
| Storage | Vercel Blob |

## Quick start

```bash
cp .env.example .env        # fill in the variables below
docker compose up --build   # FastAPI :8000, React :3000
```

Swagger UI: http://localhost:8000/docs

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `BLOB_READ_WRITE_TOKEN` | Yes | Vercel Blob token — mints short-lived client upload tokens |
| `HF_TOKEN` | No | HuggingFace API key for embeddings |
| `HF_EMBED_MODEL` | No | Embedding model (default: `sentence-transformers/all-MiniLM-L6-v2`) |
| `GEMINI_API_KEY` | No | Google Gemini API key for answer generation |
| `GEMINI_MODEL` | No | Gemini model (default: `gemini-2.5-flash`) |

Without `HF_TOKEN` / `GEMINI_API_KEY`, the app returns raw chunks but skips answer generation.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service liveness + dependency status |
| POST | `/blob-upload` | Mint a signed client token for browser → Vercel Blob upload |
| POST | `/upload-complete` | Record upload, kick off background indexing |
| GET | `/documents` | List all uploads with indexing status |
| DELETE | `/files/{filename}` | Delete a document and its chunks |
| POST | `/query` | Semantic search + Gemini answer generation |

## Smoke test

```bash
cd backend/tests && python test_end_to_end.py
```

## Vercel deployment

`vercel.json` rewrites the frontend to `/app` and the backend to `/_/backend/*`. `config.py` auto-detects `VERCEL=1` and sets the route prefix accordingly.

## Limitations

- No OCR — `pypdf` text extraction only; scanned PDFs are marked `skipped`
- No user authentication or document sharing
- Max 100 MB per PDF
