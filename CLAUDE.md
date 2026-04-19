# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All services run via Docker Compose; there is no separate "dev" build.

```bash
cp .env.example .env           # first-time setup — fill in BLOB_READ_WRITE_TOKEN and GEMINI_API_KEY
docker compose up --build      # starts fastapi (:8000), frontend (:3000), elasticsearch (:9200)
docker compose down            # keep volumes
docker compose down -v         # wipe es_data (forces a full re-index on next start)
docker compose logs -f <svc>   # svc ∈ {fastapi, frontend, elasticsearch}
```

### End-to-end retrieval test

Requires the stack to already be running on `localhost:8000`. The test cleans the index, uploads every PDF in the given directory, waits for background indexing, then scores retrieval against a QA JSON file (`{"questions": [{"question", "expected_keywords", "source_pdf"}...]}`).

```bash
cd backend/tests
python test_end_to_end.py <pdf_dir> <qa_pairs.json>
# results also written to backend/tests/results.txt
```

There is no single-test runner — the script runs all QA pairs in the JSON. To focus on one, trim the JSON.

### Frontend-only dev (rare)

Frontend normally runs inside Compose. If running `npm start` standalone on the host, the CRA `proxy` in `frontend/package.json` points at `http://fastapi:8000` (the Compose service name) and will not resolve on the host — change it to `http://localhost:8000` for host-only dev.

## Architecture

### Service wiring (backend)

Backends are constructed **once** in `src/main.py`'s `lifespan` by `init_services()` (`src/services.py`) and stashed on `app.state`. Route handlers never instantiate backends directly — they use `Depends(get_search|get_indexing|get_embeddings)` which reads from `app.state`. If you add a new backend, follow the same pattern or the background-task `IngestionPipeline` will not see it.

Upload flow is two-step: browser hits `POST /upload-url` to get a Vercel Blob upload URL + token, PUTs the PDF bytes directly to Vercel Blob, then calls `POST /upload-complete` which schedules `IngestionPipeline.index_document(filename, blob_url)` as a `BackgroundTask`. The response returns **before** indexing is complete; callers (including the e2e test) must poll `/documents` or wait. `/upload-url` currently returns dummy values — wiring it to `@vercel/blob`'s token generation is still open.

### Hybrid search (the core algorithm)

`ElasticsearchSearchBackend.hybrid_search` (`src/backends/search.py`) runs two independent ES queries over a candidate pool of `max(100, top_k * 10)`:

1. BM25 `match` with `fuzziness: AUTO, prefix_length: 1` (tolerates OCR typos) plus content highlights.
2. kNN over the `embedding` dense_vector field (cosine similarity).

Results are fused with **Reciprocal Rank Fusion**: `score(d) = Σ 1 / (RRF_K + rank)` with `RRF_K = 60`, summed across both ranked lists. The top `top_k` are returned. Docs present in only one list still get a score; docs in both rise.

### Index schema is load-bearing

`_INDEX_MAPPINGS` in `src/backends/search.py` declares the ES mapping including `embedding: dense_vector` with `dims: settings.embedding_dims` and `similarity: cosine`. Three invariants tied together:

- `EMBEDDING_DIMS` in `.env` (default 384 for `all-MiniLM-L6-v2`)
- `normalize_embeddings=True` in `TextEncoder` (`src/backends/embeddings.py`) — required because the mapping uses cosine similarity
- The ES mapping `dims` — **cannot be changed on an existing index**; swapping models requires a new `INDEX_NAME` or `docker compose down -v`

On startup the index is created if missing, or `put_mapping` is attempted if it exists — but mapping changes to `dense_vector.dims` will silently be logged as "may be out of date" and will not take effect.

### Re-index safety pattern

`IngestionPipeline.index_document` (`src/pipeline/ingestion.py`) encodes **all** batches before calling `delete_page` + re-indexing. Do not inline the delete earlier in the method: the current ordering is deliberate so that a mid-pipeline failure leaves the prior indexed version intact.

`delete_page` uses `refresh=True` so the next search immediately sees the re-index.

### Config and paths

- All config is loaded by `pydantic-settings` from `.env` via `src/config.py`. Defaults in `Settings` match the Compose network (`http://elasticsearch:9200`). For running backend outside Docker, override `ES_HOST=http://localhost:9200`.
- `src/utils/logger.py` is imported in `main.py` purely for the side effect of configuring the root logger (writes to stdout + `$LOG_DIR/app.log`, defaults to `./log`). Compose mounts `./log` into the container.
- Imports use the `src.` prefix (e.g. `from src.backends.search import ...`). Uvicorn must be invoked from `backend/` (`src.main:app`) — the Dockerfile does this; running from elsewhere breaks imports.

### Embedding model is baked into the image

`backend/Dockerfile` runs `SentenceTransformer('all-MiniLM-L6-v2')` during build to pre-download weights. Changing `EMBEDDING_MODEL` in `.env` alone will cause a cold download on first request; for reproducible builds, update the Dockerfile to match.

### Frontend

Thin React SPA (CRA). All HTTP goes through `src/api/api.js` which uses relative URLs and relies on the CRA `proxy` (see commands above). Three mounted sections: `UploadSection`, `SearchSection`, `DocumentsSection` — each owns its own state, no shared store.

## Known gaps (from README)

- Indexing is **page-level**, no sub-page chunking.
- No OCR — `pypdf`-extracted text only; scanned PDFs yield empty pages and are skipped (`text.strip()` filter in ingestion).
- `GEMINI_API_KEY` is loaded but not yet wired to any LLM step.
