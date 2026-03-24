# RAG PDF — Hybrid Semantic Search & LLM Question Answering

---

## 1. Project Description

### Problem Solved
Finding relevant information inside large PDF collections is slow and error-prone when done manually. This project solves that by letting you upload any PDF through a REST API, automatically extracting and indexing every page, and then searching across all documents instantly using full-text keyword queries — with relevance scoring and highlighted snippets.

### Tech Stack
| Layer | Technology | Role |
|---|---|---|
| API | **FastAPI** | REST endpoints — upload, search, documents |
| Object Storage | **MinIO** | Stores the original PDF files; generates presigned download URLs |
| Search Engine | **Elasticsearch** | Indexes every PDF page; powers full-text keyword search with scoring |
| PDF Parsing | **PyPDF2** | Extracts plain text from each page of a PDF |
| Configuration | **Pydantic Settings** | Loads all config from `.env` with type validation |
| Containerisation | **Docker / Docker Compose** | Runs all three services in an isolated network |
| LLM Q&A *(planned)* | **Gemini** | Will answer natural-language questions using retrieved page context |
| Semantic Search *(planned)* | **FAISS** | Will add embedding-based retrieval alongside keyword search |

---

## 2. Project Architecture

### Upload Flow
```
Client  →  POST /upload  →  MinIO (stores PDF)
                         →  Background Task
                               └── MinIO (download PDF to temp file)
                               └── PyPDF2 (extract text per page)
                               └── Elasticsearch (index each page as a document)
```
1. The client posts a PDF file to `POST /upload`.
2. The file is streamed to **MinIO** and a 1-hour presigned URL is returned immediately.
3. A **background task** kicks off without blocking the response: the PDF is re-downloaded from MinIO to a temp file, every page is extracted with PyPDF2, and each page is indexed as a separate document in Elasticsearch (fields: `filename`, `url`, `page_number`, `content`, `uploaded_at`).

### Indexing Flow
```
IndexingService.index_document(filename, url)
  └── MinioStorageBackend.download_to_tempfile()   →  /tmp/xxxx.pdf
  └── pdf.extract_text_pages()                     →  [(1, "text…"), (2, "text…"), …]
  └── ElasticsearchSearchBackend.index_page()  ×N  →  POST /pdf-index/_doc
```

### Search Flow
```
Client  →  GET /search?q=<query>&top_k=5
                └── Elasticsearch match query on `content`
                └── Returns: score, filename, page_number, url, highlights
```
- `GET /search?q=<query>` — returns ranked pages with relevance scores and highlighted snippets.
- `GET /documents` — lists all indexed documents with page count and upload time.

---

## 3. How to Run

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### Step 1 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and set your values:
```
MINIO_HOST=minio:9000
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key   # min 8 characters
MINIO_SECURE=false
BUCKET_NAME=pdf-files

ES_HOST=http://elasticsearch:9200
INDEX_NAME=pdf-index

GEMINI_API_KEY=                    # leave blank for now
```

> `MINIO_HOST` and `ES_HOST` use Docker service names. For local runs outside Docker use `localhost:9000` and `http://localhost:9200`.

### Step 2 — Start all services

```bash
docker compose up --build -d
```

| Container | Port | Role |
|---|---|---|
| `fastapi` | `8000` | REST API |
| `elasticsearch` | `9200` | Search index |
| `minio` | `9000` / `9001` | Object store / Web console |

### Step 3 — Upload a PDF

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/document.pdf"
```

```json
{
  "url": "http://localhost:9000/pdf-files/document.pdf?...",
  "status": "upload successful, indexing in progress"
}
```

### Step 4 — Search

```bash
curl "http://localhost:8000/search?q=your+query&top_k=5"
```

```json
{
  "query": "your query",
  "total": 3,
  "results": [
    {
      "score": 4.12,
      "filename": "document.pdf",
      "page_number": 2,
      "url": "...",
      "content": "...",
      "highlights": ["...matched <em>snippet</em>..."]
    }
  ]
}
```

### Step 5 — List indexed documents

```bash
curl "http://localhost:8000/documents"
```

### Step 6 — Check health

```bash
curl http://localhost:8000/health
```

### Step 7 — Stop services

```bash
docker compose down          # stop containers
docker compose down -v       # stop + delete all stored data
```

### Running locally without Docker

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

> MinIO and Elasticsearch must still be running (e.g. via Docker) for the API to work.

---

## 4. Project Structure

```
.
├── config.py             # Loads and validates all settings from .env using Pydantic
├── docker-compose.yml    # Defines the fastapi, elasticsearch, and minio services
├── Dockerfile            # Builds the FastAPI container image
├── requirements.txt      # Python package dependencies
│
└── src/
    ├── main.py           # FastAPI app — registers all routes (/upload, /search, /documents, /health)
    ├── setup.py          # Builds backend instances at startup; provides FastAPI Depends() factories
    ├── storage.py        # MinioStorageBackend — handles PDF upload, download, and presigned URLs
    ├── search.py         # ElasticsearchSearchBackend — creates index, indexes pages, runs search queries
    ├── indexing.py       # IndexingService — orchestrates download → text extraction → indexing pipeline
    ├── pdf.py            # extract_text_pages() — reads a local PDF and yields (page_number, text) tuples
    └── logger.py         # Configures root logger to write to stdout and log/app.log
```