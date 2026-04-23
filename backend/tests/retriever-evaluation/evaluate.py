#!/usr/bin/env python3
"""
Usage:
    python backend/tests/evaluate.py --qa qa.json
    python backend/tests/evaluate.py --qa qa.json --top-k 5 --out results.json
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


def chunk_relevant(chunk_tokens: set, keywords: list[str]) -> bool:
    """A chunk is relevant if it contains at least one expected keyword phrase."""
    return any(tokens(kw).issubset(chunk_tokens) for kw in keywords)


def load_qa(path: str) -> list[dict]:
    """Accept both [{question, answer}] and {questions:[{question, expected_keywords}]}."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return [{"question": d["question"], "keywords": [d["answer"]]} for d in data]
    return [{"question": d["question"], "keywords": d["expected_keywords"]} for d in data["questions"]]


def evaluate(api, qa, mode, top_k):
    precision_scores, recall_scores = [], []
    for item in qa:
        keywords = item["keywords"]
        try:
            chunks = requests.post(f"{api}/query", json={"question": item["question"], "top_k": top_k, "search_mode": mode}, timeout=60).json().get("chunks") or []
        except Exception:
            chunks = []
        relevant = sum(1 for c in chunks if chunk_relevant(tokens(c.get("content", "")), keywords))
        precision_scores.append(relevant / len(chunks) if chunks else 0)
        recall_scores.append(1.0 if relevant > 0 else 0.0)
    return precision_scores, recall_scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa", required=True)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    qa = load_qa(args.qa)
    n = len(qa)

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
        p_scores, r_scores = evaluate(args.api, qa, mode, args.top_k)
        p = sum(p_scores) / n
        r = sum(r_scores) / n
        f1 = 2 * p * r / (p + r) if (p + r) else 0
        hits = int(r * n)
        print(f"{mode:<12} {p:>11.1%}  {r:>8.1%} ({hits}/{n})  {f1:>6.1%}")
        results[mode] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
                         "per_question": [{"id": qa[i].get("id", i+1), "precision": p_scores[i], "recall": r_scores[i]} for i in range(n)]}

    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved to {args.out}")

if __name__ == "__main__":
    sys.exit(main() or 0)
