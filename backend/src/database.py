import logging
import re
from datetime import datetime, timezone
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from src.config import settings

_CREATE_UPLOADS_TABLE = """
CREATE TABLE IF NOT EXISTS uploads (
    filename TEXT PRIMARY KEY,
    blob_url TEXT NOT NULL DEFAULT '',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending',
    page_count INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_VECTOR_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector;"

_CREATE_CHUNKS_TABLE = f"""
CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    filename TEXT NOT NULL REFERENCES uploads(filename) ON DELETE CASCADE,
    page INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector({settings.embed_dim}) NOT NULL
);
"""

_ADD_TSVECTOR_COLUMN = """
ALTER TABLE chunks
  ADD COLUMN IF NOT EXISTS content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS chunks_filename_idx ON chunks(filename);",
    "CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING ivfflat (embedding vector_cosine_ops);",
    "CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN (content_tsv);",
]



class PostgreSQLStorageManager:
    """All PostgreSQL access: upload records and searchable text chunks."""

    @staticmethod
    def _to_pg_vector(values: list[float]) -> str:
        return "[" + ",".join(f"{float(v):.7f}" for v in values) + "]"

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool
        self._create_tables()

    @classmethod
    def create(cls) -> "PostgreSQLStorageManager":
        url = settings.database_url.strip()
        if not url:
            raise ValueError("DATABASE_URL is not set.")
        pool = ConnectionPool(
            conninfo=url,
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
            open=True,
            kwargs={"autocommit": False, "prepare_threshold": None},
        )
        return cls(pool)

    def _create_tables(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(_CREATE_UPLOADS_TABLE)
            conn.commit()
        with self._pool.connection() as conn:
            try:
                conn.execute(_CREATE_VECTOR_EXTENSION)
                conn.execute(_CREATE_CHUNKS_TABLE)
                conn.execute(_ADD_TSVECTOR_COLUMN)
                for stmt in _CREATE_INDEXES:
                    conn.execute(stmt)
                conn.commit()
            except Exception:
                conn.rollback()
                logging.exception(
                    "pgvector extension not available; /query will fail until it is installed"
                )

    def _run(self, sql: str, params: tuple) -> None:
        with self._pool.connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def ping(self) -> bool:
        try:
            with self._pool.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            logging.exception("Database ping failed")
            return False

    # --- Upload records ---

    def add_upload(self, filename: str, blob_url: str) -> None:
        self._run(
            """
            INSERT INTO uploads (filename, blob_url, uploaded_at, status, page_count)
            VALUES (%s, %s, %s, 'pending', 0)
            ON CONFLICT (filename) DO UPDATE SET
                blob_url = EXCLUDED.blob_url,
                uploaded_at = EXCLUDED.uploaded_at,
                status = 'pending',
                page_count = 0
            """,
            (filename, blob_url, datetime.now(timezone.utc)),
        )

    def set_status(self, filename: str, status: str, page_count: int = 0) -> None:
        self._run(
            "UPDATE uploads SET status = %s, page_count = %s WHERE filename = %s",
            (status, page_count, filename),
        )

    def remove_upload(self, filename: str) -> None:
        with self._pool.connection() as conn:
            cur = conn.execute(
                "DELETE FROM uploads WHERE filename = %s RETURNING filename", (filename,)
            )
            deleted = cur.fetchone()
            conn.commit()
        if not deleted:
            raise KeyError(filename)

    def list_uploads(self) -> list[dict]:
        sql = """
            SELECT u.filename, u.blob_url, u.uploaded_at, u.status, u.page_count,
                   COALESCE(c.chunk_count, 0) AS chunk_count
            FROM uploads u
            LEFT JOIN (
                SELECT filename, COUNT(*) AS chunk_count FROM chunks GROUP BY filename
            ) c ON c.filename = u.filename
            ORDER BY u.uploaded_at DESC NULLS LAST
        """
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql)
                rows = cur.fetchall()

        out: list[dict] = []
        for r in rows:
            chunk_count = int(r["chunk_count"] or 0)
            uploaded_at: datetime | None = r["uploaded_at"]
            out.append(
                {
                    "filename": r["filename"],
                    "blob_url": r["blob_url"] or "",
                    "page_count": int(r["page_count"] or 0),
                    "chunk_count": chunk_count,
                    "uploaded_at": uploaded_at.isoformat() if uploaded_at else None,
                    "status": r["status"] or "pending",
                    "embedded": chunk_count > 0,
                }
            )
        return out

    # --- Text chunks ---

    def save_chunks(
        self,
        filename: str,
        pages: list[int],
        indexes: list[int],
        texts: list[str],
        vectors: list[list[float]],
    ) -> None:
        if not texts:
            return
        rows = [
            (filename, page, idx, text, self._to_pg_vector(vec))
            for page, idx, text, vec in zip(pages, indexes, texts, vectors)
        ]
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (filename, page, chunk_index, content, embedding) "
                    "VALUES (%s, %s, %s, %s, %s::vector)",
                    rows,
                )
            conn.commit()

    def delete_chunks(self, filename: str) -> None:
        self._run("DELETE FROM chunks WHERE filename = %s", (filename,))

    @staticmethod
    def _to_tsquery(text: str, op: str = "&") -> str:
        tokens = re.findall(r"[A-Za-z0-9]+", text)
        joined = f" {op} ".join(tokens)
        return joined if tokens else "placeholder"

    def search_chunks(
        self,
        query_vector: list[float],
        query_text: str = "",
        k: int = 5,
        filenames: list[str] | None = None,
        search_mode: str = "hybrid",
    ) -> list[dict]:
        vec = self._to_pg_vector(query_vector)

        if search_mode == "semantic" or not query_text.strip():
            return self._search_semantic(vec, k, filenames)

        if search_mode == "keyword":
            return self._search_keyword(query_text, k, filenames)

        return self._search_hybrid(vec, query_text, k, filenames)

    def _search_semantic(
        self,
        vec: str,
        k: int,
        filenames: list[str] | None,
    ) -> list[dict]:
        sql = (
            "SELECT filename, page, chunk_index, content, "
            "1 - (embedding <=> %s::vector) AS score FROM chunks "
        )
        params: list = [vec]
        if filenames:
            sql += "WHERE filename = ANY(%s) "
            params.append(filenames)
        sql += "ORDER BY embedding <=> %s::vector LIMIT %s"
        params.extend([vec, k])

        with self._pool.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        logging.info("search(semantic): %d/%d chunks (filter=%s, k=%d)", len(rows), total, filenames, k)
        return [
            {
                "filename": r["filename"],
                "page": int(r["page"]),
                "chunk_index": int(r["chunk_index"]),
                "content": r["content"],
                "score": float(r["score"]),
            }
            for r in rows
        ]

    def _search_keyword(
        self,
        query_text: str,
        k: int,
        filenames: list[str] | None,
    ) -> list[dict]:
        # OR-joined tsquery so any matching token surfaces a result
        tsq = self._to_tsquery(query_text, op="|")
        sql = (
            "SELECT filename, page, chunk_index, content, "
            "ts_rank(content_tsv, to_tsquery('english', %s)) AS score "
            "FROM chunks "
        )
        params: list = [tsq]
        conditions = ["content_tsv @@ to_tsquery('english', %s)"]
        params.append(tsq)
        if filenames:
            conditions.append("filename = ANY(%s)")
            params.append(filenames)
        sql += "WHERE " + " AND ".join(conditions) + " "
        sql += "ORDER BY score DESC LIMIT %s"
        params.append(k)

        with self._pool.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        logging.info("search(keyword): %d/%d chunks (filter=%s, k=%d, tsq=%r)", len(rows), total, filenames, k, tsq)
        return [
            {
                "filename": r["filename"],
                "page": int(r["page"]),
                "chunk_index": int(r["chunk_index"]),
                "content": r["content"],
                "score": float(r["score"]),
            }
            for r in rows
        ]

    def _search_hybrid(
        self,
        vec: str,
        query_text: str,
        k: int,
        filenames: list[str] | None,
    ) -> list[dict]:
        tsq = self._to_tsquery(query_text)
        pool_size = k * 4

        filename_filter = "filename = ANY(%(filenames)s)" if filenames else "TRUE"

        sql = f"""
            WITH
              vec AS (
                SELECT id, filename, page, chunk_index, content,
                       ROW_NUMBER() OVER (ORDER BY embedding <=> %(vec)s::vector) AS rn
                FROM chunks
                WHERE {filename_filter}
                ORDER BY embedding <=> %(vec)s::vector
                LIMIT %(pool)s
              ),
              fts AS (
                SELECT id, filename, page, chunk_index, content,
                       ROW_NUMBER() OVER (ORDER BY ts_rank(content_tsv, query) DESC) AS rn
                FROM chunks, to_tsquery('english', %(tsq)s) query
                WHERE {filename_filter}
                  AND content_tsv @@ query
                ORDER BY ts_rank(content_tsv, query) DESC
                LIMIT %(pool)s
              ),
              fused AS (
                SELECT
                  COALESCE(v.id, f.id)                  AS id,
                  COALESCE(v.filename, f.filename)       AS filename,
                  COALESCE(v.page, f.page)               AS page,
                  COALESCE(v.chunk_index, f.chunk_index) AS chunk_index,
                  COALESCE(v.content, f.content)         AS content,
                  COALESCE(1.0 / (60 + v.rn), 0)
                    + COALESCE(1.0 / (60 + f.rn), 0)    AS score
                FROM vec v
                FULL OUTER JOIN fts f ON f.id = v.id
              )
            SELECT * FROM fused
            ORDER BY score DESC
            LIMIT %(k)s
        """

        params: dict = {
            "vec": vec,
            "tsq": tsq,
            "pool": pool_size,
            "k": k,
            "filenames": filenames,
        }

        with self._pool.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        logging.info("search(hybrid): %d/%d chunks (filter=%s, k=%d, tsq=%r)", len(rows), total, filenames, k, tsq)
        return [
            {
                "filename": r["filename"],
                "page": int(r["page"]),
                "chunk_index": int(r["chunk_index"]),
                "content": r["content"],
                "score": float(r["score"]),
            }
            for r in rows
        ]
