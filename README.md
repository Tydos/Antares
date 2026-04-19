# RAG PDF

Upload PDFs to **Vercel Blob** from the browser. The backend records each upload in **PostgreSQL**, downloads the file as a background task, and uses **pypdf** to count pages with extractable text.

## Quickstart

```bash
cp .env.example .env   # fill in DATABASE_URL and BLOB_READ_WRITE_TOKEN
docker compose up --build
```

| Service  | Port | Notes   |
| -------- | ---- | ------- |
| fastapi  | 8000 | `/docs` |
| frontend | 3000 | Web UI  |

## Environment variables

| Variable               | Required | Description                          |
| ---------------------- | -------- | ------------------------------------ |
| `DATABASE_URL`         | Yes      | PostgreSQL connection string          |
| `BLOB_READ_WRITE_TOKEN`| Yes      | Vercel Blob read/write token          |

## API

| Endpoint            | Method | Description                                        |
| ------------------- | ------ | -------------------------------------------------- |
| `/blob-upload`      | POST   | Vercel Blob handle-upload → `clientToken`          |
| `/upload-complete`  | POST   | `{ filename, blobUrl }` — schedules background processing |
| `/documents`        | GET    | List uploads and ingestion status                  |
| `/files/{filename}` | DELETE | Remove upload row                                  |
| `/health`           | GET    | API + database status                              |

## Smoke test

```bash
cd backend/tests
python test_end_to_end.py
```

## Limitations

- No OCR — `pypdf`-extracted text only; scanned PDFs are marked `skipped`.
- No search or retrieval layer.
