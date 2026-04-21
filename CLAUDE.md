# CLAUDE.md

## Commands

```bash
cp .env.example .env           # fill DATABASE_URL, BLOB_READ_WRITE_TOKEN, HF_TOKEN
docker compose up --build      # fastapi (:8000), frontend (:3000)
docker compose down
docker compose logs -f <svc>   # svc ∈ {fastapi, frontend}
```

Smoke test (requires the stack on `localhost:8000`):

```bash
cd backend/tests && python test_end_to_end.py
```

## Architecture

Entry point: `backend/src/main.py`. Services (`Database`, `Pipeline`) are initialised once in `lifespan` and stored on `app.state`; route handlers inject them via `Depends`.

```
backend/src/
  main.py             routes, lifespan startup
  config.py           pydantic settings (auto-sets route prefix on Vercel)
  database.py         postgres + pgvector — uploads table + chunks table
  ingestion_service.py download → pdf_parser.py → embedding.py → database.py
  embedding.py        HuggingFace Inference API (384-dim cosine vectors)
  generator.py        HuggingFace LLM answer generation with chunk citations
  create_upload_token.py HMAC-SHA256 client token minting (1-hour TTL)
  pdf_parser.py       pypdf text extraction, 800-char chunks / 100-char overlap
  interfaces.py       Protocol definitions for Database, Embedder, Extractor, Generator
  schemas.py          Pydantic request/response models
  utils.py            LatencyTracker helper
```

## Upload flow

1. Browser calls `/request_upload_token` → backend mints a signed Vercel Blob client token.
2. `@vercel/blob` SDK uploads the PDF directly from the browser to blob storage.
3. Browser calls `/upload-complete` with `{filename, blobUrl}`.
4. Backend inserts a `pending` row in `uploads` and schedules `Pipeline.index_document` as a `BackgroundTask`.
5. Background task: download → pypdf extract → chunk → embed (HuggingFace) → store in `chunks` (pgvector) → set status `indexed` / `skipped` / `failed`.

## Query flow

1. Browser POSTs `{question, top_k, filenames?}` to `/query`.
2. Backend embeds the question, runs pgvector cosine search (`<=>`) on `chunks`.
3. Top-k chunks are passed to `answerer.py` → HuggingFace LLM generates a cited answer.
4. Response includes both the answer and the raw chunks (filename, page, score).

## Note on Vercel deployment

`config.py` auto-sets `route_prefix = /_/backend` when `VERCEL=1`. `vercel.json` rewrites public paths to that prefix.
