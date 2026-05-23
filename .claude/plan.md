# PatchWatch — Plan

Add a Cybersec tab to the existing Antares RAG system. The PDF chat tab is
untouched. The new tab ingests security advisories from OSV/GitHub/NVD into
the same vector store and lets users query them.

---

## What We're Building

```
Existing:   Chat tab  → /query (source_type=pdf)   → PDF chunks
New:     Cybersec tab → /query (source_type=advisory) → advisory chunks
                      → /ingest/package → OSV + GitHub + NVD → advisory chunks
```

Same database, same embedding pipeline, same query endpoint — just a new
`source_type` column that scopes results per tab.

---

## What We Touch

| File | Change |
|---|---|
| `frontend/src/components/Navbar.js` | Add Cybersec tab button |
| `frontend/src/App.js` | Add `view === 'cybersec'` branch |
| `frontend/src/api/api.js` | Add `ingestPackage`, `listPackages`, `queryAdvisories` |
| `backend/src/schemas.py` | Add `source_type` field to `QueryRequest` |
| `backend/src/storage/chunks.py` | Add `source_type` filter to `search_chunks` |
| `backend/src/main.py` | Add `/ingest/package`, `/ingest/status`, `/packages` routes |
| DB | `ALTER TABLE chunks ADD COLUMN source_type`, `ADD COLUMN advisory_id` |

## What We Don't Touch

Everything else — `ChatSection`, `UploadSection`, `DocumentsSection`,
`EvalDashboard`, `pdf_parser.py`, blob upload routes, `/chat`, `/history`.

---

## New Files

```
frontend/src/components/
  CybersecSection.js       # new tab UI

backend/src/
  advisories/
    __init__.py
    osv.py                 # OSV.dev API client
    github.py              # GitHub Security Advisories GraphQL client
    nvd.py                 # NVD CVSS enrichment
    ingestion.py           # fetches advisories → chunks → embeds → stores
    schemas.py             # Advisory, AffectedRange pydantic models
```

---

## What to Ingest

### Sources (in priority order)

| Source | Provides | Auth | Cost |
|---|---|---|---|
| **OSV.dev** | Affected version ranges, fix version, CVE/GHSA IDs, severity | None | Free |
| **GitHub Security Advisories** | Rich prose descriptions, CWEs, patch references | `GITHUB_TOKEN` | Free |
| **NVD (NIST)** | CVSS v3 vector, attack vector, exploitability detail | `NVD_API_KEY` | Free |

Start with OSV + GitHub Advisories. NVD is additive enrichment — adds CVSS
detail that OSV sometimes omits.

### 3 Chunks Per Advisory

Each CVE/GHSA is split into three chunks so queries hit the right content:

**Chunk 1 — Identity + Severity**
```
Package: pillow (PyPI)
CVE: CVE-2023-44271  |  GHSA: GHSA-j7hp-h8jx-5ppr
Severity: HIGH (CVSS 7.5)
Affected: >= 10.0.0, < 10.0.1  |  Fixed in: 10.0.1
```
Answers: "Is my version affected?" / "What's the minimum safe version?"

**Chunk 2 — Description**

Full prose from GitHub Security Advisory — what the vulnerability is, how it
is triggered, and what the impact is.

Answers: "What does this CVE do?" / "Is this exploitable remotely?"

**Chunk 3 — Technical Detail + Resolution**
```
Attack vector: Network  |  Complexity: Low  |  Privileges required: None
CWE: CWE-400 (Uncontrolled Resource Consumption)
Workaround: Validate image dimensions before processing.
Patch: github.com/python-pillow/Pillow/pull/7315
```
Answers: "What's the attack vector?" / "Is there a workaround?"

### What NOT to Ingest

- Raw CVE JSON blobs — too noisy for semantic search
- NVD reference link lists — no prose, won't embed usefully
- Advisories duplicated across OSV and GitHub — deduplicate on CVE ID before storing
- CVSS numbers without prose context — numbers alone don't cluster meaningfully

### Seed Package List

Index these on first deploy. Covers ~80% of real-world Python CVEs:

```
requests, urllib3, cryptography, pillow, django, flask, sqlalchemy,
paramiko, pyyaml, lxml, jinja2, werkzeug, setuptools, aiohttp, httpx,
numpy, certifi
```

---

## DB Migration

```sql
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'pdf';
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS advisory_id TEXT;
```

`source_type` scopes search results per tab — `'pdf'` for the existing chat
tab, `'advisory'` for the cybersec tab. Existing rows get `'pdf'` by default,
so the chat tab behavior is unchanged.

---

## Backend Changes

### `schemas.py` — add one field to `QueryRequest`
```python
class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    filenames: list[str] | None = None
    search_mode: str = "hybrid"
    source_type: str | None = None   # new — None means no filter (existing behavior)
```

### `storage/chunks.py` — add `source_type` filter

Pass it through to the SQL `WHERE` clause alongside the existing `filenames`
filter. No other changes to `search_chunks`.

### `main.py` — three new routes

```python
POST /ingest/package
# Body: {"name": "pillow", "ecosystem": "PyPI"}
# Triggers background ingestion. Returns immediately.
# {"status": "ingestion started", "package": "pillow"}

GET /packages
# Lists all packages with advisory chunks in the DB.
# {"packages": [{"name": "pillow", "ecosystem": "PyPI", "advisory_count": 12, "last_ingested": "..."}]}

DELETE /packages/{name}
# Removes all advisory chunks for a package.
```

The existing `/query` endpoint is reused by the cybersec tab — it just passes
`source_type: "advisory"` in the request body.

---

## Frontend Changes

### `Navbar.js` — add one button

```jsx
<button
  className={`navbar-link${view === 'cybersec' ? ' active' : ''}`}
  onClick={() => onViewChange('cybersec')}
>
  <ShieldIcon />
  Cybersec
</button>
```

### `App.js` — add one branch

```jsx
{view === 'cybersec' ? (
  <CybersecSection />
) : view === 'chat' ? (
  <div className="app-layout"> ... </div>
) : (
  <EvalDashboard messages={messages} />
)}
```

### `CybersecSection.js` — new component

Two-panel layout matching the existing chat tab style:

**Left sidebar:**
- Package input (name + ecosystem dropdown: PyPI / npm / Go / crates.io)
- "Scan Package" button → calls `POST /ingest/package` → shows progress
- List of indexed packages (from `GET /packages`) with last-ingested timestamp and delete button

**Main panel:**
- Chat interface (reuses same message UI as `ChatSection`)
- Queries call `POST /query` with `source_type: "advisory"` and `search_mode: "hybrid"`
- Suggested starter questions shown when no messages yet:
  - "What CVEs affect pillow 9.1.0?"
  - "What is the minimum safe version of cryptography?"
  - "Does requests have any RCE vulnerabilities?"
  - "Are there workarounds for CVE-2023-44271?"

### `api.js` — three new functions

```js
export const ingestPackage = (name, ecosystem) =>
  postJSON(`${API}/ingest/package`, { name, ecosystem });

export const listPackages = () =>
  request(`${API}/packages`).then((d) => d.packages);

export const deletePackage = (name) =>
  request(`${API}/packages/${encodeURIComponent(name)}`, { method: 'DELETE' });

// /query is reused — call the existing `query()` with source_type added:
export const queryAdvisories = (question, { topK = 5, searchMode = 'hybrid' } = {}) =>
  postJSON(`${API}/query`, {
    question,
    top_k: topK,
    search_mode: searchMode,
    source_type: 'advisory',
  });
```

---

## Config Changes (`config.py`)

```python
# Add:
github_token: str = ""       # read:security_events scope
nvd_api_key: str = ""        # free at nvd.nist.gov
osv_timeout: int = 10
```

---

## Sequence of Work

1. **DB migration** — add `source_type` and `advisory_id` columns
2. **`chunks.py`** — add `source_type` filter to `search_chunks`
3. **`schemas.py`** — add `source_type` to `QueryRequest`
4. **`advisories/osv.py`** — OSV client, test with `pillow`
5. **`advisories/github.py`** — GitHub Advisory GraphQL client
6. **`advisories/nvd.py`** — NVD CVSS enrichment
7. **`advisories/ingestion.py`** — wire clients → chunks → embed → store
8. **`main.py`** — add `/ingest/package`, `/packages`, `DELETE /packages/{name}`
9. **`CybersecSection.js`** — new frontend tab component
10. **`Navbar.js` + `App.js`** — wire the new tab
11. **`api.js`** — add the three new API functions
12. **Ingest seed list** — run ingestion for the 18 seed packages, test the 4 sample questions
