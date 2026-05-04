# Performance Bottleneck Analysis: RAG-PDF (Antares)

## Context

The system is a RAG pipeline for PDF question-answering. It ingests PDFs via Vercel Blob, chunks and embeds them via HuggingFace Inference API, stores vectors in PostgreSQL (pgvector), and retrieves with hybrid RRF search before generating answers with Llama-3.2-1B. The goal of this plan is to identify where latency and throughput suffer most, and define concrete mitigation strategies.

---

## Bottleneck Inventory (Ranked by Impact)

### 1. LLM Generation — ~500ms–2s (40–80% of total latency)
**File:** `backend/src/inference/generator.py`

- Synchronous blocking call to HF Inference API (`_client.chat.completions.create(...)`)
- Full answer must complete before any bytes reach the user
- Small 1B model (Llama-3.2-1B-Instruct) is slow on shared HF infrastructure
- No streaming, no prompt caching, no token budget management for context

**Strategies:**
- **Stream LLM output via SSE:** Implement `StreamingResponse` in FastAPI + `stream=True` on the HF client. Frontend consumes SSE tokens as they arrive — eliminates the perceived wait.
- **Upgrade model or use direct inference:** Llama-3.2-1B is low-quality and often cold-starts on HF. Moving to Claude Haiku (already used for eval) via the Anthropic API would give better quality *and* lower latency due to predictable SLAs.
- **Trim context before generation:** Count tokens (tiktoken is already in requirements.txt) and truncate chunks to fit a fixed budget (e.g., 1,500 tokens), rather than concatenating all chunk text blindly. Smaller prompts = faster generation.

---

### 2. Query Embedding — ~100–500ms, uncached (runs on every request)
**File:** `backend/src/inference/embedding.py`, `backend/src/main.py:124-125`

- Every `/query` and `/chat` request makes a remote HTTP call to embed the question
- No caching at any layer; identical questions re-embed every time
- Fixed batch size of 32 for ingestion; query embedding is a batch of 1

**Strategies:**
- **In-memory embedding cache:** LRU cache keyed by `sha256(question.lower().strip())`. Cache hit ratio will be high for repeated/similar queries. Since the embedding model is deterministic, this is safe.
- **Local embedding model:** Replace HF Inference API with `sentence-transformers` running in-process. Adds ~100MB memory but removes network round-trip entirely (~5–20ms vs ~100–500ms).
- **Larger/better embedding model:** `all-MiniLM-L6-v2` (384-dim) is fast but low-fidelity. Upgrading to `all-mpnet-base-v2` (768-dim) or `e5-base-v2` would improve retrieval quality (recall in evals was poor: 30–40% for semantic).

---

### 3. No Response Caching — repeated queries pay full cost every time
**File:** `backend/src/main.py` (no cache exists anywhere)

- Identical or semantically equivalent questions re-run embed → search → LLM
- Eval shows the system is used with a fixed gold set; many repeated queries

**Strategies:**
- **Exact-match response cache:** `dict` keyed by `(question, search_mode, top_k, frozenset(filenames))` with a TTL. Zero-cost for exact repeats.
- **Semantic cache (advanced):** Cache responses indexed by embedding; serve cached answer if cosine similarity to a prior query exceeds 0.95. Useful when users rephrase the same question.

---

### 4. Synchronous Ingestion Pipeline — blocks worker thread on large PDFs
**File:** `backend/src/ingestion/service.py`

- `urllib.request.urlretrieve(blob_url, tmp.name)` — synchronous download (can be seconds for large PDFs)
- Embedding loop: `for i in range(0, len(texts), 32): self._fetch_embeddings(...)` — sequential HTTP calls, no parallelism
- A 40-page PDF with 5 chunks/page = 200 chunks → 7 sequential embed batches (~700ms–3.5s)
- Background task runs in the same thread pool as request handlers (FastAPI default)

**Strategies:**
- **Concurrent embedding batches:** Use `asyncio.gather()` or `concurrent.futures.ThreadPoolExecutor` to send multiple embedding batches in parallel. For 7 batches, parallel execution reduces embedding time by ~5×.
- **Async download:** Switch `urllib.request.urlretrieve` to `aiohttp` or `httpx.AsyncClient` for non-blocking download.
- **Dedicated worker process:** Move ingestion to a Celery/RQ worker or a separate thread pool to isolate it from request-serving threads.

---

### 5. Wasteful Message History Loading
**File:** `backend/src/main.py:194`, `backend/src/storage/messages.py`

- `db.get_messages()` loads the last 50 messages from the database on every `/chat` request
- Only the last 6 turns are used: `history[-6:]` (hardcoded in `generator.py:24`)
- 50 messages means 50 rows of TEXT + JSONB fetched and deserialized for no benefit

**Strategy:**
- Pass `limit=6` (or at most 10 for safety margin) to `get_messages()`. This is a one-line fix with immediate benefit.

---

### 6. Disabled Prepared Statement Cache
**File:** `backend/src/storage/database.py:37`

```python
kwargs={"autocommit": False, "prepare_threshold": None}
```

- `prepare_threshold=None` disables psycopg's prepared statement caching
- The hybrid search SQL query is long (~30 lines); re-parsing on every request wastes PostgreSQL planning time

**Strategy:**
- Remove `"prepare_threshold": None` or set it to `5`. Psycopg will cache the plan after 5 executions of the same query, reducing per-query overhead by ~5–10ms for complex queries.

---

### 7. Full-Table COUNT on Every Search (for debug logging)
**File:** `backend/src/storage/chunks.py` (inside `_search_semantic`, `_search_keyword`, `_search_hybrid`)

- `SELECT COUNT(*) FROM chunks` is executed before every search solely for logging
- Full sequential scan on large tables; IVFFlat doesn't help COUNT(*)

**Strategy:**
- Remove the COUNT query. Log `len(rows)` instead, without the denominator. If total chunk count is needed for observability, cache it with a short TTL.

---

### 8. Character-Based Chunking (Quality/Recall Issue)
**File:** `backend/src/ingestion/pdf_parser.py`, `backend/src/config.py:26-27`

- 800-char fixed sliding window splits mid-sentence, mid-table, mid-list
- Contributes to poor retrieval recall (30–40% in evals)
- Low recall forces retrieval of irrelevant chunks, bloating LLM context

**Strategies:**
- **RecursiveCharacterTextSplitter (LangChain-style):** Split on paragraph breaks → sentence breaks → word breaks, in priority order. Keeps semantic units intact.
- **Sentence-aware chunking:** Use spaCy or NLTK sentence tokenizer; group sentences into chunks that respect a token (not character) budget.
- **Semantic chunking:** Embed each sentence, detect embedding-space discontinuities, split at topic boundaries. Highest quality but most compute-intensive.

---

### 9. IVFFlat Index Not Tuned
**File:** `backend/src/storage/chunks.py` (CREATE INDEX statement)

```sql
CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops);
```

- Default `lists` parameter (100) may be poorly sized for the actual corpus
- For small corpora (<10K chunks): reduce `lists` to `sqrt(n_chunks)` ≈ 50–100
- For large corpora (>100K chunks): increase `lists` to `n_chunks / 1000`

**Strategy:**
- After indexing is complete, run `SET ivfflat.probes = 10;` at query time (currently 1 by default) for better recall at minor latency cost.
- Monitor corpus size and rebuild index with appropriate `lists` value.

---

## Prioritized Implementation Plan

| Priority | Bottleneck | File(s) | Effort | Impact |
|---|---|---|---|---|
| 1 | Limit message history fetch | `main.py:194`, `messages.py` | 1 line | Low/Medium |
| 2 | Remove COUNT(*) from search | `chunks.py` | 2 lines | Low |
| 3 | Re-enable prepared statements | `database.py:37` | 1 line | Low |
| 4 | In-memory query embedding cache | `main.py`, `embedding.py` | ~20 lines | High |
| 5 | Stream LLM output via SSE | `generator.py`, `main.py`, `api.js` | Medium (~100 lines) | Very High |
| 6 | Parallel embedding batches (ingestion) | `ingestion/service.py`, `embedding.py` | Medium | High |
| 7 | Token-aware context trimming | `generator.py` | Small (~20 lines) | Medium |
| 8 | Semantic/sentence-aware chunking | `pdf_parser.py` | Medium | High (recall) |
| 9 | Local embedding model | `embedding.py` + Dockerfile | Large | High |
| 10 | Upgrade LLM (Claude Haiku) | `generator.py`, config | Medium | Very High |

---

## Critical Files to Modify

- `backend/src/main.py` — query/chat endpoint logic, history limit
- `backend/src/inference/generator.py` — LLM call, streaming, context trimming
- `backend/src/inference/embedding.py` — caching, local model, parallel batches
- `backend/src/ingestion/service.py` — async ingestion, parallel embed
- `backend/src/storage/chunks.py` — remove COUNT(*), add ivfflat.probes
- `backend/src/storage/database.py` — re-enable prepared statement cache
- `backend/src/ingestion/pdf_parser.py` — semantic chunking
- `frontend/src/api/api.js` — SSE consumer
- `frontend/src/components/ChatSection.js` — streaming token display

---

## Verification

1. **Latency:** The existing `LatencyTracker` (`backend/src/utils/latency.py`) already tracks `embed`, `search`, `llm`, `total`. Measure before/after each change. The EvalDashboard shows this live.
2. **Retrieval quality:** Run `backend/tests/retriever-evaluation/evaluate.py` — target Recall@5 ≥ 60% (up from 30–40%).
3. **Answer quality:** Run `backend/tests/retriever-evaluation/answer_quality.py` — target Faithfulness ≥ 0.75 (up from 0.56).
4. **Correctness:** Run `pytest backend/tests/` to ensure no regressions.
5. **Streaming:** Manually test `/chat` endpoint in the UI to verify tokens appear incrementally.
