# RAG PDF — Hybrid Semantic Search & LLM Q&A

## 1. Overview

Finding information in large PDFs can be slow. This project lets you upload PDFs, automatically extract text from each page, and search across all documents instantly using **hybrid search** — combining keyword search (BM25) and semantic similarity (kNN) with **Reciprocal Rank Fusion (RRF)**.

### Key Features

* PDF upload and automated text extraction.
* Embedding of page content for semantic search.
* Hybrid search using BM25 and kNN with Reciprocal Rank Fusion (RRF).
* API endpoints for upload, search, document listing, and health checks.
* Optional LLM integration for context-aware Q&A.

---

## 2. Technology Stack

| Layer             | Technology                                   | Purpose                                                                    |
| ----------------- | -------------------------------------------- | -------------------------------------------------------------------------- |
| Backend API       | FastAPI                                      | Provides REST endpoints for document upload, search, and health checks     |
| Frontend          | React                                        | UI for PDF upload, search, and document management                         |
| Object Storage    | MinIO                                        | Persistent storage of uploaded PDF files                                   |
| Search Engine     | Elasticsearch 8.17                           | Page-level indexing and hybrid search (BM25 + kNN)                         |
| Embeddings        | `sentence-transformers` (`all-MiniLM-L6-v2`) | Converts text into 384-dimensional vector embeddings                       |
| PDF Parsing       | pypdf                                        | Extracts plaintext from PDF pages                                          |
| Configuration     | Pydantic                                     | Loads and validates environment variables from `.env`                      |
| Containerization  | Docker / Docker Compose                      | Deploys backend, frontend, Elasticsearch, and MinIO in an isolated network |
| LLM Q&A (planned) | Gemini                                       | Provides natural language answers using retrieved document context         |

---

## 3. Architecture

### 3.1 Upload Workflow

1. Client uploads PDF via `POST /upload`.
2. PDF is stored in MinIO.
3. Background pipeline:

   * Downloads PDF from MinIO to temporary storage.
   * Extracts text per page using `pypdf`.
   * Converts page text to embeddings in batches.
   * Indexes pages in Elasticsearch with text content and embeddings.

**Flow Diagram:**

```
Client  →  POST /upload  →  MinIO (store PDF)
                         →  Background Task:
                               └─ Download PDF
                               └─ Extract page text
                               └─ Encode pages → embeddings
                               └─ Index in Elasticsearch
```

### 3.2 Search Workflow

1. Client queries via `GET /search?q=<query>&top_k=N`.
2. Query is converted into a vector embedding.
3. Elasticsearch performs:

   * BM25 keyword search.
   * kNN vector search over embeddings.
4. Results are merged using Reciprocal Rank Fusion (RRF) and re-ranked.
5. Top N results are returned with scores, highlights, and metadata.

**Flow Diagram:**

```
Client  →  GET /search?q=<query>
       └─ Encode query → vector
       └─ Elasticsearch BM25 search → keyword hits
       └─ Elasticsearch kNN search → semantic hits
       └─ Merge & re-rank with RRF
       └─ Return top_k results with score, highlights, metadata
```

---

## 4. Source Structure

```
backend/
├─ Dockerfile
├─ requirements.txt
└─ src/
   ├─ main.py          # FastAPI routes
   ├─ config.py        # Pydantic settings loader
   ├─ services.py      # Dependency injection for backends
   ├─ backends/
   │   ├─ search.py    # ElasticsearchSearchBackend
   │   ├─ storage.py   # MinioStorageBackend
   │   └─ embeddings.py # TextEncoder wrapper
   ├─ pipeline/
   │   └─ ingestion.py  # PDF ingestion pipeline
   └─ utils/
       ├─ pdf_reader.py # Page-level text extraction
       └─ logger.py     # Logging configuration

frontend/
├─ Dockerfile
└─ src/
   ├─ App.js
   ├─ api/api.js        # HTTP request wrappers
   └─ components/
       ├─ UploadSection.js
       ├─ SearchSection.js
       └─ DocumentsSection.js
```

---

## 5. Deployment Instructions

### 5.1 Prerequisites

* Docker and Docker Compose installed.

### 5.2 Configuration

Copy example environment file:

```bash
cp .env.example .env
```

Edit `.env` if needed:

```dotenv
MINIO_HOST=minio:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123
MINIO_SECURE=false
BUCKET_NAME=pdf-files

ES_HOST=http://elasticsearch:9200
INDEX_NAME=pdf-index

EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMS=384
BATCH_SIZE=16

GEMINI_API_KEY=        # reserved for LLM
```

### 5.3 Start Services

```bash
docker compose up --build
```

| Service       | Port        | Notes                 |
| ------------- | ----------- | --------------------- |
| fastapi       | 8000        | API docs: `/docs`     |
| frontend      | 3000        | Web UI                |
| elasticsearch | 9200        | Backend search engine |
| minio         | 9000 / 9001 | Web UI: 9001          |

### 5.4 Stop Services

```bash
docker compose down        # Stop containers, keep data
docker compose down -v     # Stop containers + remove volumes
```

---

## 6. API Endpoints

| Endpoint            | Method | Description                                      |
| ------------------- | ------ | ------------------------------------------------ |
| `/upload`           | POST   | Upload a PDF; triggers background indexing       |
| `/search`           | GET    | Query PDFs; returns top_k page results           |
| `/documents`        | GET    | List all indexed documents with embedding status |
| `/health`           | GET    | Check service health                             |
| `/files/{filename}` | GET    | Download stored PDF                              |

---

## 7. Hybrid Search Details

* **Candidate Pool:** For each query, retrieve up to `max(100, top_k × 10)` candidates.
* **BM25 Search:** Keyword-based, handles OCR errors via fuzziness, returns highlighted matches.
* **kNN Search:** Cosine similarity over 384-dimensional embeddings, captures semantic similarity.
* **Reciprocal Rank Fusion (RRF):** Combines ranks from BM25 and kNN to generate final score:

$$
\text{score}(d) = \sum_{\text{lists}} \frac{1}{k + \text{rank}(d)}, \quad k = 60
$$

* Higher scores indicate stronger relevance.

This approach ensures retrieval accounts for both exact word matches and semantic meaning.
