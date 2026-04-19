import logging
from datetime import datetime, timezone

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.config import settings


_CREATE_UPLOADS = """
CREATE TABLE IF NOT EXISTS uploads (
    filename TEXT PRIMARY KEY,
    blob_url TEXT NOT NULL DEFAULT '',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending',
    page_count INTEGER NOT NULL DEFAULT 0
);
"""


class DocumentStore:
    """PostgreSQL persistence for Vercel Blob upload metadata and ingestion status."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(_CREATE_UPLOADS)
            conn.commit()

    def ping(self) -> bool:
        try:
            with self._pool.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            logging.exception("Database ping failed")
            return False

    def record_upload(self, filename: str, blob_url: str) -> None:
        now = datetime.now(timezone.utc)
        with self._pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO uploads (filename, blob_url, uploaded_at, status, page_count)
                VALUES (%s, %s, %s, 'pending', 0)
                ON CONFLICT (filename) DO UPDATE SET
                    blob_url = EXCLUDED.blob_url,
                    uploaded_at = EXCLUDED.uploaded_at,
                    status = 'pending',
                    page_count = 0
                """,
                (filename, blob_url, now),
            )
            conn.commit()

    def set_upload_status(self, filename: str, status: str, page_count: int = 0) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "UPDATE uploads SET status = %s, page_count = %s WHERE filename = %s",
                (status, page_count, filename),
            )
            conn.commit()

    def delete_upload_record(self, filename: str) -> None:
        with self._pool.connection() as conn:
            cur = conn.execute("DELETE FROM uploads WHERE filename = %s RETURNING filename", (filename,))
            deleted = cur.fetchone()
            conn.commit()
        if not deleted:
            raise FileNotFoundError(filename)

    def list_documents(self) -> list[dict]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT filename, blob_url, uploaded_at, status, page_count "
                    "FROM uploads ORDER BY uploaded_at DESC NULLS LAST"
                )
                rows = cur.fetchall()

        out: list[dict] = []
        for r in rows:
            pc = int(r["page_count"] or 0)
            st = r["status"] or "pending"
            ua: datetime | None = r["uploaded_at"]
            out.append(
                {
                    "filename": r["filename"],
                    "blob_url": r.get("blob_url") or "",
                    "page_count": pc,
                    "uploaded_at": ua.isoformat() if ua else None,
                    "status": st,
                    "embedded": st == "indexed" and pc > 0,
                }
            )
        return out


def create_pool() -> ConnectionPool:
    url = settings.database_url.strip()
    if not url:
        raise ValueError("DATABASE_URL is not set.")
    return ConnectionPool(conninfo=url, min_size=1, max_size=10, open=True, kwargs={"autocommit": False})
