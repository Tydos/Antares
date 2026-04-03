#!/usr/bin/env python3
"""
Stress test: Upload multiple PDFs and evaluate retrieval using QA pairs.
Returns: Precision@5, Recall@5, Retrieval Accuracy
Cleans the index before running so only target PDFs are searched.
"""

import sys
import time
import json
import requests
import logging
from pathlib import Path

TEST_DIR = Path(__file__).parent
RESULTS_FILE = TEST_DIR / "results.txt"

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler(str(RESULTS_FILE), mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8000"


def clean_index():
    """Delete all existing documents from the index."""
    logger.info("Cleaning index...")
    response = requests.get(f"{API_BASE}/documents")
    docs = response.json().get("documents", [])
    for doc in docs:
        try:
            requests.delete(f"{API_BASE}/files/{doc['filename']}")
        except Exception:
            pass
    logger.info(f"  Removed {len(docs)} existing documents\n")


def upload_pdfs(pdf_dir):
    """Upload all PDFs from a directory."""
    pdf_dir = Path(pdf_dir)
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    logger.info(f"Uploading {len(pdf_files)} PDFs from {pdf_dir.name}/\n")

    uploaded = 0
    for pdf_path in pdf_files:
        logger.info(f"  Uploading: {pdf_path.name}")
        try:
            with open(pdf_path, "rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                response = requests.post(f"{API_BASE}/upload", files=files)
            if response.status_code == 200:
                uploaded += 1
            else:
                logger.error(f"    Failed: {response.text}")
        except Exception as e:
            logger.error(f"    Error: {e}")

    logger.info(f"\n  Uploaded {uploaded}/{len(pdf_files)} PDFs\n")
    return uploaded > 0


def wait_for_indexing(expected_docs):
    """Wait for all PDFs to be indexed."""
    logger.info("Waiting for indexing...")
    time.sleep(max(15, expected_docs * 5))

    response = requests.get(f"{API_BASE}/documents")
    docs = response.json().get("documents", [])
    total_pages = sum(d.get("page_count", 0) for d in docs)
    logger.info(f"  Indexed {len(docs)} document(s), {total_pages} page(s)\n")

    for d in docs:
        logger.info(f"    {d['filename']}: {d['page_count']} pages")
    logger.info("")
    return True


def run_evaluation(qa_pairs):
    """Run queries and evaluate retrieval."""
    logger.info("=" * 60)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 60 + "\n")

    results = []

    for idx, qa in enumerate(qa_pairs, 1):
        question = qa.get("question")
        expected_keywords = qa.get("expected_keywords", [])
        source_pdf = qa.get("source_pdf", "")

        logger.info(f"Q{idx}: {question}")
        logger.info(f"  Source: {source_pdf}")

        try:
            response = requests.get(
                f"{API_BASE}/search",
                params={"q": question, "top_k": 5}
            )

            if response.status_code != 200:
                logger.error(f"  Search failed: {response.text}\n")
                continue

            retrieved = response.json().get("results", [])
            n_retrieved = len(retrieved)

            if n_retrieved == 0:
                logger.info("  No results returned\n")
                results.append({"precision": 0, "recall": 0, "retrieval_accuracy": 0, "source_found": False})
                continue

            # Calculate relevance per result
            relevance_scores = []
            source_found = False
            for rank, doc in enumerate(retrieved, 1):
                content = doc.get("content", "").lower()
                filename = doc.get("filename", "")
                kw_matches = sum(1 for kw in expected_keywords if kw.lower() in content)
                relevance = kw_matches / len(expected_keywords) if expected_keywords else 0
                relevance_scores.append(relevance)
                if filename == source_pdf:
                    source_found = True

            # Precision: fraction of retrieved that are relevant
            precision = sum(1 for r in relevance_scores if r > 0) / n_retrieved

            # Recall: best keyword coverage in any single result
            recall = max(relevance_scores) if relevance_scores else 0

            # Retrieval accuracy: average keyword coverage
            retrieval_accuracy = sum(relevance_scores) / n_retrieved

            source_tag = "YES" if source_found else "NO"
            logger.info(f"  Retrieved: {n_retrieved} | Precision: {precision:.1%} | Recall: {recall:.1%} | Accuracy: {retrieval_accuracy:.1%} | Source found: {source_tag}\n")

            results.append({
                "precision": precision,
                "recall": recall,
                "retrieval_accuracy": retrieval_accuracy,
                "source_found": source_found
            })

        except Exception as e:
            logger.error(f"  Error: {e}\n")
            continue

    # Summary
    if results:
        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        avg_precision = sum(r["precision"] for r in results) / len(results)
        avg_recall = sum(r["recall"] for r in results) / len(results)
        avg_accuracy = sum(r["retrieval_accuracy"] for r in results) / len(results)
        source_hit_rate = sum(1 for r in results if r.get("source_found")) / len(results)

        logger.info(f"Total Questions:       {len(results)}")
        logger.info(f"Average Precision@5:   {avg_precision:.1%}")
        logger.info(f"Average Recall@5:      {avg_recall:.1%}")
        logger.info(f"Retrieval Accuracy:    {avg_accuracy:.1%}")
        logger.info(f"Source Doc Hit Rate:   {source_hit_rate:.1%}")
        logger.info("=" * 60)


def main(pdf_dir, json_file):
    """Main workflow."""
    logger.info("Starting multi-PDF stress test...\n")

    pdf_path = Path(pdf_dir).resolve()
    json_path = Path(json_file).resolve()

    if not pdf_path.is_dir():
        logger.error(f"PDF directory not found: {pdf_dir}")
        return

    if not json_path.exists():
        logger.error(f"JSON file not found: {json_file}")
        return

    try:
        with open(json_path, "r") as f:
            qa_data = json.load(f)
        qa_pairs = qa_data.get("questions", [])
        logger.info(f"Loaded {len(qa_pairs)} Q&A pairs\n")
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        return

    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code != 200:
            logger.error("FastAPI health check failed")
            return
        logger.info("FastAPI healthy\n")
    except Exception as e:
        logger.error(f"Cannot connect to FastAPI: {e}")
        return

    clean_index()

    pdf_count = len(list(pdf_path.glob("*.pdf")))
    if not upload_pdfs(pdf_dir):
        return

    if not wait_for_indexing(pdf_count):
        return

    run_evaluation(qa_pairs)
    logger.info("Stress test completed!")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_end_to_end.py <pdf_directory> <json_file>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
