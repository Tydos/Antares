import logging

from src.interfaces import DatabaseProtocol, EmbedderProtocol

from .osv import fetch_advisories
from .schemas import Advisory


def advisory_filename(name: str, ecosystem: str) -> str:
    return f"advisory::{name}::{ecosystem}"


class AdvisoryIngestionService:
    def __init__(self, db: DatabaseProtocol, embedder: EmbedderProtocol) -> None:
        self._db = db
        self._embedder = embedder

    async def ingest_package(self, name: str, ecosystem: str) -> int:
        filename = advisory_filename(name, ecosystem)
        self._db.add_upload(filename, f"advisory://{ecosystem}/{name}")

        try:
            advisories = await fetch_advisories(name, ecosystem)
            if not advisories:
                self._db.set_status(filename, "indexed", 0)
                return 0

            texts, pages, indexes, advisory_ids = [], [], [], []
            for adv_idx, adv in enumerate(advisories):
                for chunk_idx, chunk_text in enumerate(_to_chunks(adv)):
                    texts.append(chunk_text)
                    pages.append(adv_idx)
                    indexes.append(chunk_idx)
                    advisory_ids.append(adv.id)

            vectors = self._embedder.embed(texts)
            self._db.delete_chunks(filename)
            self._db.save_advisory_chunks(filename, pages, indexes, texts, vectors, advisory_ids)
            self._db.set_status(filename, "indexed", len(advisories))
            logging.info(
                "Ingested %s (%s): %d advisories, %d chunks",
                name, ecosystem, len(advisories), len(texts),
            )
            return len(advisories)

        except Exception:
            logging.exception("Advisory ingestion failed for %s (%s)", name, ecosystem)
            self._db.set_status(filename, "failed", 0)
            return 0


def _to_chunks(adv: Advisory) -> list[str]:
    cve_ids = [a for a in adv.aliases if a.startswith("CVE-")]
    primary_id = cve_ids[0] if cve_ids else adv.id

    ranges_str = ", ".join(
        ">= " + (r.introduced or "0") + (f", < {r.fixed}" if r.fixed else " (unfixed)")
        for r in adv.affected_ranges
    ) or "unknown"

    # Chunk 1 — identity + severity (answers "am I affected?" / "what's the fix?")
    identity = (
        f"Package: {adv.package} ({adv.ecosystem})\n"
        f"ID: {adv.id}"
        + (f"  |  CVE: {primary_id}" if primary_id != adv.id else "") + "\n"
        f"Severity: {adv.severity or 'unknown'}\n"
        f"Affected versions: {ranges_str}\n"
        f"Fixed in: {adv.fixed_version or 'no fix available'}\n"
        f"Published: {adv.published or 'unknown'}"
    )

    chunks = [identity]

    # Chunk 2 — description prose (answers "what does this vulnerability do?")
    prose = adv.details.strip() or adv.summary.strip()
    if prose:
        chunks.append(
            f"Vulnerability description for {primary_id} ({adv.package}):\n{prose}"
        )

    # Chunk 3 — references (answers "where's the patch?" / "are there workarounds?")
    if adv.references:
        refs_text = "\n".join(f"- {r}" for r in adv.references)
        chunks.append(
            f"Patch and reference links for {primary_id} ({adv.package}):\n{refs_text}"
        )

    return chunks
