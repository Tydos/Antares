# RAG PDF — Hybrid Semantic Search & LLM Q&A

## 1. Overview

Finding information in large PDFs can be slow. This project lets you upload PDFs, automatically extract text from each page, and search across all documents instantly using **hybrid search** — combining keyword search (BM25) and semantic similarity (kNN) with **Reciprocal Rank Fusion (RRF)**.

### Key Features

* PDF upload and automated text extraction.
* Embedding of page content for semantic search (via Hugging Face Inference API).
* Hybrid search using BM25 and kNN with Reciprocal Rank Fusion (RRF).
* API endpoints for upload, search, document listing, and health checks.
* Optional LLM integration for context-aware Q&A.

---

## 2. Technology Stack

| Layer             | Technology                                   | Purpose                                                                    |
| ----------------- | -------------------------------------------- | -------------------------------------------------------------------------- |
| Backend API       | FastAPI                                      | REST endpoints for blob token minting, upload completion, search, health |
| Frontend          | React (`@vercel/blob` client)                | UI for PDF upload, search, and document management                         |
| Object Storage    | Vercel Blob                                  | Browser uploads PDFs directly to blob storage (public read for indexing)   |
| Search Engine     | Elasticsearch 8.17                           | Page-level indexing and hybrid search (BM25 + kNN)                         |
| Embeddings        | Hugging Face Inference (`huggingface_hub`)   | Remote feature extraction (default: `sentence-transformers/all-MiniLM-L6-v2`, 384-dim) |
| PDF Parsing       | pypdf                                        | Extracts plaintext from PDF pages                                          |
| Configuration     | Pydantic Settings                            | Loads and validates environment variables from `.env`                        |
| Containerization  | Docker / Docker Compose                      | Backend, frontend, and Elasticsearch in an isolated network                |
| LLM Q&A (planned) | Gemini                                       | Natural language answers using retrieved document context                    |

---

## 3. Architecture

### 3.1 Upload Workflow

1. Browser uses `@vercel/blob/client` `upload()` with `handleUploadUrl` pointing at **`POST /blob-upload`**.
2. Backend mints a **client token** (HMAC using `BLOB_READ_WRITE_TOKEN`) compatible with Vercel Blob’s handle-upload protocol.
3. The SDK uploads PDF bytes directly to Vercel Blob (public access so the indexer can download by URL).
4. Client calls **`POST /upload-complete`** with `pathname` and `blobUrl` from the upload result.
5. Background pipeline: download PDF from `blobUrl` → extract text per page → embed via Hugging Face → index in Elasticsearch.

**Flow Diagram:**

```
Browser  →  POST /blob-upload (blob.generate-client-token)  →  { clientToken }
        →  @vercel/blob uploads bytes to Vercel Blob
        →  POST /upload-complete { filename, blobUrl }
        →  Background: download PDF → pypdf → HF embeddings → Elasticsearch
```

Indexing runs asynchronously; poll **`GET /documents`** until the new file appears.

### 3.2 Search Workflow

1. Client queries via `GET /search?q=<query>&top_k=N`.
2. Query is embedded via the Hugging Face Inference API.
3. Elasticsearch runs BM25 and kNN, merges with RRF, returns top N page-level hits.

**Flow Diagram:**

```
Client  →  GET /search?q=<query>
       └─ HF Inference → query vector
       └─ Elasticsearch BM25 + kNN → RRF merge
       └─ Return top_k results with score, highlights, metadata
```

---

## 4. Source Structure

```
backend/
├─ Dockerfile
├─ requirements.txt
└─ src/
   ├─ main.py              # FastAPI routes
   ├─ config.py            # Pydantic settings
   ├─ services.py          # App-wide backends
   ├─ blob_client_token.py # Vercel Blob client-token minting
   ├─ backends/
   │   ├─ search.py        # ElasticsearchSearchBackend
   │   └─ embeddings.py    # Hugging Face InferenceClient wrapper
   ├─ pipeline/
   │   └─ ingestion.py     # PDF ingestion pipeline
   └─ utils/
       ├─ pdf_reader.py
       └─ logger.py

frontend/
├─ Dockerfile
└─ src/
   ├─ App.js
   ├─ api/api.js           # Vercel Blob upload + API helpers
   └─ components/
       ├─ UploadSection.js
       ├─ SearchSection.js
       └─ DocumentsSection.js
```

---

## 5. Deployment Instructions

### 5.1 Prerequisites

* Docker and Docker Compose.
* A [Hugging Face access token](https://huggingface.co/settings/tokens) with permission to call **Inference Providers** (fine-grained: “Make calls to Inference Providers”, or a classic token with inference access).
* A Vercel Blob store and **`BLOB_READ_WRITE_TOKEN`** (from the Vercel project or `vercel env pull`).

### 5.2 Configuration

Copy the example env file:

```bash
cp .env.example .env
```

Edit `.env`. Important variables:

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `HUGGINGFACE_API_TOKEN` | Yes (for search & indexing) | HF token for `InferenceClient` embeddings |
| `BLOB_READ_WRITE_TOKEN` | Yes (for uploads) | Vercel Blob read/write token |
| `ES_HOST` | No | Default `http://elasticsearch:9200` in Compose |
| `INDEX_NAME` | No | Default `pdf-index` |
| `EMBEDDING_MODEL` | No | Hub model id (default `sentence-transformers/all-MiniLM-L6-v2`) |
| `EMBEDDING_DIMS` | No | Must match index mapping (default `384`) |
| `BATCH_SIZE` | No | Embedding batch size (default `16`) |
| `HUGGINGFACE_INFERENCE_URL` | No | Optional override for InferenceClient `model` (full URL or model id) |
| `GEMINI_API_KEY` | No | Reserved for future LLM Q&A |

### 5.3 Start Services

```bash
docker compose up --build -d
```

| Service       | Port | Notes                 |
| ------------- | ---- | --------------------- |
| fastapi       | 8000 | API docs: `/docs`     |
| frontend      | 3000 | Web UI (proxies API in dev) |
| elasticsearch | 9200 | Search backend        |

### 5.4 Stop Services

```bash
docker compose down        # Stop containers, keep volumes
docker compose down -v     # Stop and remove Elasticsearch data volume
```

---

## 6. API Endpoints

| Endpoint            | Method | Description |
| ------------------- | ------ | ----------- |
| `/blob-upload`      | POST   | Vercel Blob handle-upload body → returns `clientToken` for browser upload |
| `/upload-complete`  | POST   | `{ filename, blobUrl }` — schedules background indexing |
| `/search`           | GET    | `q`, `top_k` — hybrid search over indexed pages |
| `/documents`        | GET    | List indexed documents |
| `/health`           | GET    | Elasticsearch reachability + API status |
| `/files/{filename}` | DELETE | Remove a document from the index |

---

## 7. Hybrid Search Details

* **Candidate pool:** Up to `max(100, top_k × 10)` candidates per query.
* **BM25:** Keyword search with optional fuzziness and highlights.
* **kNN:** Cosine similarity on dense vectors (384 dimensions by default).
* **RRF:** Combines BM25 and kNN ranks with \(k = 60\).

---

## 8. Testing & Evaluation

### 8.1 End-to-End Test Script

```bash
cd backend/tests
python test_end_to_end.py <pdf_directory> <qa_pairs_json>
```

Note: the script’s upload path may expect a legacy multipart endpoint; align it with the current **`/blob-upload` + `/upload-complete`** flow if you extend automated uploads.

### 8.2 Metrics (when using the evaluation script)

Precision@5, Recall@5, retrieval accuracy, and source document hit rate — see `backend/tests/test_end_to_end.py`.

---

## 9. Known Limitations & Future Work

* **Page-level indexing** — No sub-page chunking.
* **LLM Q&A** — Not wired in the main UI; `GEMINI_API_KEY` is reserved.
* **Scanned PDFs** — Depends on extractable text from `pypdf`.
* **Embeddings** — Requires network access to Hugging Face Inference (or a custom `HUGGINGFACE_INFERENCE_URL`).

Future: chunking, Gemini Q&A, cross-encoder reranking, richer PDF/OCR support.

---

## 10. Troubleshooting

### Services fail to start

* Ensure Docker is running and ports **8000**, **3000**, **9200** are free.
* Logs: `docker compose logs -f fastapi`

### FastAPI exits or search fails with embedding errors

* Set **`HUGGINGFACE_API_TOKEN`** and ensure the token can call **Inference Providers**.
* If you see HTTP errors from Hugging Face, confirm **`EMBEDDING_MODEL`** exists on the Hub and supports feature extraction.

### Upload fails

* Set **`BLOB_READ_WRITE_TOKEN`** and ensure the Vercel Blob store exists.
* Frontend must reach **`POST /blob-upload`** (same origin in Docker Compose via the dev proxy on port 3000).

### Search returns no results

* `GET /documents` — confirm pages were indexed after upload.
* `GET /health` — Elasticsearch should be reachable.
