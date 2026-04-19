# CLAUDE.md

## Commands

```bash
cp .env.example .env           # fill DATABASE_URL, BLOB_READ_WRITE_TOKEN
docker compose up --build      # fastapi (:8000), frontend (:3000)
docker compose down
docker compose logs -f <svc>   # svc ∈ {fastapi, frontend}
```

Smoke test (requires the stack on `localhost:8000`):

```bash
cd backend/tests && python test_end_to_end.py
```

## Upload flow

1. Browser POSTs to `/blob-upload` → backend mints a client token from `BLOB_READ_WRITE_TOKEN`.
2. `@vercel/blob` uploads the PDF directly to blob storage.
3. Browser POSTs to `/upload-complete` with `filename` + `blobUrl`.
4. Backend inserts a `pending` row in PostgreSQL and runs `IngestionPipeline.index_document` as a `BackgroundTask` (download → pypdf → set status `indexed`/`skipped`/`failed`).

Entry point: `backend/src/main.py`. Services are initialised once in `lifespan` via `services.py` and stored on `app.state`; route handlers inject them with `Depends(get_store|get_indexing)`.

## Note on Vercel deployment

`config.py` auto-sets `route_prefix = /_/backend` when `VERCEL=1`. `vercel.json` rewrites public paths to that prefix.
