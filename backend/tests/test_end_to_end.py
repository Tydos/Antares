#!/usr/bin/env python3
"""
Simplified end-to-end test: Upload PDF and evaluate using QA pairs from JSON.
Results logged to results.txt
"""

import sys
import time
import json
import requests
import logging
from pathlib import Path

# Get test directory and results file path
TEST_DIR = Path(__file__).parent
RESULTS_FILE = TEST_DIR / "results.txt"

# Configure logging to both console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(RESULTS_FILE)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8000"


def upload_pdf(pdf_path):
    """Upload PDF file to FastAPI backend."""
    logger.info(f"Uploading PDF: {pdf_path}")
    
    with open(pdf_path, "rb") as f:
        files = {"file": (Path(pdf_path).name, f, "application/pdf")}
        response = requests.post(f"{API_BASE}/upload", files=files)
    
    if response.status_code != 200:
        logger.error(f"Upload failed: {response.text}")
        return False
    
    logger.info(f"✓ Upload successful")
    return True


def wait_for_indexing():
    """Wait for PDF to be indexed."""
    logger.info("Waiting for indexing...")
    time.sleep(5)
    
    response = requests.get(f"{API_BASE}/documents")
    docs = response.json().get("documents", [])
    logger.info(f"✓ Indexed {len(docs)} documents")
    return True


def run_evaluation(qa_pairs):
    """Run queries from QA pairs and evaluate retrieval."""
    logger.info("\n" + "=" * 80)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 80 + "\n")
    
    results = []
    
    for idx, qa in enumerate(qa_pairs, 1):
        question = qa.get("question")
        expected_keywords = qa.get("expected_keywords", [])
        
        logger.info(f"Q{idx}: {question}")
        
        try:
            response = requests.get(
                f"{API_BASE}/search",
                params={"q": question, "top_k": 5}
            )
            
            if response.status_code != 200:
                logger.error(f"Search failed: {response.text}\n")
                continue
            
            result = response.json()
            retrieved = result.get("results", [])
            
            # Calculate relevance scores
            relevance_scores = []
            for rank, doc in enumerate(retrieved[:5], 1):
                content = doc.get("content", "").lower()
                keyword_matches = sum(1 for kw in expected_keywords if kw.lower() in content)
                relevance = keyword_matches / len(expected_keywords) if expected_keywords else 0
                relevance_scores.append(relevance)
                
                logger.info(f"  [{rank}] Page {doc.get('page_number')} | Relevance: {relevance:.1%}")
            
            # Calculate metrics
            precision = sum(1 for r in relevance_scores if r > 0) / len(relevance_scores) if relevance_scores else 0
            avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
            
            logger.info(f"  Precision@5: {precision:.1%} | Avg Relevance: {avg_relevance:.1%}\n")
            
            results.append({
                "question": question,
                "precision": precision,
                "avg_relevance": avg_relevance
            })
            
        except Exception as e:
            logger.error(f"Error: {e}\n")
            continue
    
    # Summary
    if results:
        logger.info("=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        avg_precision = sum(r["precision"] for r in results) / len(results)
        avg_relevance = sum(r["avg_relevance"] for r in results) / len(results)
        
        logger.info(f"Total Questions: {len(results)}")
        logger.info(f"Average Precision@5: {avg_precision:.1%}")
        logger.info(f"Average Relevance Score: {avg_relevance:.1%}")
        logger.info("=" * 80)


def main(pdf_file, json_file):
    """Main workflow."""
    logger.info("Starting end-to-end retrieval test...\n")
    
    # Validate inputs and resolve paths
    pdf_path = Path(pdf_file).resolve()
    json_path = Path(json_file).resolve()
    
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_file}")
        return
    
    if not json_path.exists():
        logger.error(f"JSON file not found: {json_file}")
        return
    
    # Load QA pairs
    try:
        with open(json_path, "r") as f:
            qa_data = json.load(f)
        qa_pairs = qa_data.get("questions", [])
        logger.info(f"Loaded {len(qa_pairs)} Q&A pairs from {json_file}\n")
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        return
    
    # Check API
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code != 200:
            logger.error("FastAPI health check failed")
            return
        logger.info(f"✓ FastAPI healthy\n")
    except Exception as e:
        logger.error(f"Cannot connect to FastAPI: {e}")
        return
    
    # Upload PDF
    if not upload_pdf(pdf_file):
        return
    
    # Wait for indexing
    if not wait_for_indexing():
        return
    
    # Run evaluation
    run_evaluation(qa_pairs)
    
    logger.info("\n✓ Test completed successfully!")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_end_to_end.py <pdf_file> <json_file>")
        print("Example: python test_end_to_end.py document.pdf qa_pairs.json")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    json_file = sys.argv[2]
    
    main(pdf_file, json_file)
