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

---

## 8. Testing & Evaluation

### 8.1 Run the End-to-End Test

The test suite evaluates retrieval quality by uploading PDFs, running QA queries, and reporting metrics.

```bash
cd backend/tests
python test_end_to_end.py <pdf_directory> <qa_pairs_json>
```

Example:

```bash
python test_end_to_end.py ./input input/qa_pairs.json
```

### 8.2 Test Metrics

The test reports four metrics for each query and averages across all queries:

1. **Precision@5** — Fraction of top-5 results containing relevant keywords (%)
2. **Recall@5** — Best keyword coverage found in any single top-5 result (%)
3. **Retrieval Accuracy** — Average keyword coverage across all top-5 results (%)
4. **Source Doc Hit Rate** — Percentage of queries where the correct source document appears in top-5 (%)

### 8.3 Expected Results

For a well-tuned system with clean index:
- Precision@5: 60-100%
- Recall@5: 80-100%
- Retrieval Accuracy: 50-100%
- Source Doc Hit Rate: 80-100%

### 8.4 Test Files

- `backend/tests/test_end_to_end.py` — Main test script
- `backend/tests/qa_pairs.json` — 20 QA pairs across 6 documents
- `backend/tests/input/` — Test PDF directory
- `backend/tests/results.txt` — Latest test output

---

## 9. Known Limitations & Future Work

### Current Limitations

- **Page-level indexing only** — No sub-page chunking means single-page documents become one index entry.
- **No LLM integration yet** — Q&A uses retrieved text only; full LLM-based answers are reserved for future work.
- **Limited OCR support** — Relies on pypdf text extraction; scanned PDFs may fail.

### Future Improvements

- Sub-page chunking (e.g., sentence-level or semantic splitting) to improve precision.
- LLM integration (Gemini) for context-aware natural language Q&A.
- Fine-tuning embeddings on domain-specific data.
- Advanced ranking models (e.g., cross-encoders) for re-ranking results.
- Support for multi-modal documents (images, tables).

---

## 10. Troubleshooting

### Services fail to start

- Check Docker daemon is running.
- Verify ports 8000, 3000, 9200, 9000 are not in use.
- Review logs: `docker compose logs -f <service_name>`

### Search returns no results

- Confirm PDFs are indexed: `GET /documents`
- Check Elasticsearch health: `GET /health`
- Verify query text matches document content (keyword matching is case-insensitive but must match extracted text).

### Low retrieval accuracy

- Clean the index and re-upload PDFs.
- Adjust `top_k` parameter (default: 5).
- Review QA pair keywords to ensure they match actual document text.
