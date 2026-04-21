import logging
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

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS chunks_filename_idx ON chunks(filename);",
    "DROP INDEX IF EXISTS chunks_embedding_idx;",
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
            try:
                conn.execute(_CREATE_VECTOR_EXTENSION)
            except Exception:
                conn.rollback()
                logging.exception(
                    "pgvector extension not available; /query will fail until it is installed"
                )
            else:
                conn.execute(_CREATE_CHUNKS_TABLE)
                for stmt in _CREATE_INDEXES:
                    conn.execute(stmt)
            conn.commit()

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
            raise FileNotFoundError(filename)

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

    def search_chunks(
        self,
        query_vector: list[float],
        k: int = 5,
        filenames: list[str] | None = None,
    ) -> list[dict]:
        vec = self._to_pg_vector(query_vector)
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

        logging.info(f"search: {len(rows)}/{total} chunks (filter={filenames}, k={k})")
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
