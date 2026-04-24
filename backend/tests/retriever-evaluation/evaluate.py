#!/usr/bin/env python3
"""
Evaluate retrieval quality against a QA file or gold set.

Supported input formats:
  1. Gold set (from generate_gold_set.py):
       [{"question", "ground_truth", "ground_truth_contexts", "source_pdf", "page"}, ...]
  2. Keyword format:
       {"questions": [{"question", "expected_keywords", "source_pdf"}, ...]}
  3. Simple list:
       [{"question", "answer"}, ...]

Usage:
    python evaluate.py --qa tests/retriever-evaluation/qa_pairs.json
    python evaluate.py --qa tests/evaluation/gold_set.json --top-k 5 --out results.json
"""

import argparse
import json
import re
import sys
import requests

MODES = ["hybrid", "semantic", "keyword"]
STOPWORDS = {"a","an","the","of","in","to","and","or","for","is","was","be","with","at","by","his","her","on"}


def tokens(text):
    words = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def chunk_relevant(chunk_content: str, references: list[str], is_gold: bool) -> bool:
    """
    Gold set: chunk is relevant if token overlap with any ground_truth_context >= 50%.
    Keyword format: chunk must contain all tokens of at least one keyword phrase.
    """
    chunk_tok = tokens(chunk_content)
    if not chunk_tok:
        return False
    if is_gold:
        for ref in references:
            ref_tok = tokens(ref)
            if not ref_tok:
                continue
            overlap = len(chunk_tok & ref_tok) / len(ref_tok)
            if overlap >= 0.5:
                return True
        return False
    return any(tokens(kw).issubset(chunk_tok) for kw in references)


def load_qa(path: str) -> tuple[list[dict], bool]:
    """
    Returns (qa_list, is_gold).
    Each qa_list item: {"question": str, "references": [str], ...metadata}
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Gold set: list with ground_truth_contexts key
    if isinstance(data, list) and data and "ground_truth_contexts" in data[0]:
        qa = [
            {
                "question": d["question"],
                "references": d["ground_truth_contexts"],
                "source_pdf": d.get("source_pdf", ""),
                "page": d.get("page"),
            }
            for d in data
        ]
        return qa, True

    # Keyword format: {"questions": [...]}
    if isinstance(data, dict) and "questions" in data:
        qa = [
            {
                "question": d["question"],
                "references": d["expected_keywords"],
                "source_pdf": d.get("source_pdf", ""),
            }
            for d in data["questions"]
        ]
        return qa, False

    # Simple list: [{"question", "answer"}]
    qa = [{"question": d["question"], "references": [d["answer"]]} for d in data]
    return qa, False


def evaluate(api, qa, is_gold, mode, top_k):
    precision_scores, recall_scores = [], []
    for item in qa:
        try:
            resp = requests.post(
                f"{api}/query",
                json={"question": item["question"], "top_k": top_k, "search_mode": mode},
                timeout=60,
            ).json()
            chunks = resp.get("chunks") or []
        except Exception:
            chunks = []

        relevant = sum(
            1 for c in chunks
            if chunk_relevant(c.get("content", ""), item["references"], is_gold)
        )
        precision_scores.append(relevant / len(chunks) if chunks else 0)
        recall_scores.append(1.0 if relevant > 0 else 0.0)

    return precision_scores, recall_scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa", required=True, help="Path to QA file (gold set or keyword format)")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    args = parser.parse_args()

    qa, is_gold = load_qa(args.qa)
    n = len(qa)
    fmt = "gold set" if is_gold else "keyword"
    print(f"Loaded {n} questions ({fmt} format)")

    try:
        h = requests.get(f"{args.api}/health", timeout=10)
        body = h.json()
        if body.get("services", {}).get("database") is False:
            print("Warning: database unhealthy — results may be empty")
    except requests.exceptions.ConnectionError as e:
        print(f"API unreachable: {e}")
        return 1

    results = {}
    print(f"\n{'MODE':<12} {'Precision@k':>12} {'Recall@k':>10} {'F1':>8}")
    print("-" * 46)
    for mode in MODES:
        p_scores, r_scores = evaluate(args.api, qa, is_gold, mode, args.top_k)
        p = sum(p_scores) / n
        r = sum(r_scores) / n
        f1 = 2 * p * r / (p + r) if (p + r) else 0
        hits = int(r * n)
        print(f"{mode:<12} {p:>11.1%}  {r:>8.1%} ({hits}/{n})  {f1:>6.1%}")
        results[mode] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "per_question": [
                {"id": i + 1, "question": qa[i]["question"], "precision": p_scores[i], "recall": r_scores[i]}
                for i in range(n)
            ],
        }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    sys.exit(main() or 0)
