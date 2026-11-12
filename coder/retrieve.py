"""Candidate retrieval using offline pre-built BM25 index."""

import os
import pickle
import re
from rank_bm25 import BM25Okapi

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "coder", "data", "bm25_index.pkl")
NON_ALPHANUM = re.compile(r"[^a-z0-9]+")

_INDEX_CACHE = None


def load_index():
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        if not os.path.exists(INDEX_PATH):
            raise FileNotFoundError(f"BM25 index not found at {INDEX_PATH}. Run coder/build_index.py first.")
        with open(INDEX_PATH, "rb") as f:
            _INDEX_CACHE = pickle.load(f)
    return _INDEX_CACHE


CONVERSATIONAL_STOPWORDS = {
    "doctor", "patient", "clinician", "dr", "pt", "hello", "good", "morning", "afternoon",
    "what", "brings", "today", "how", "are", "you", "doing", "have", "had", "has", "having",
    "since", "many", "yes", "no", "small", "maybe", "started", "any", "just", "your",
    "is", "was", "were", "am", "been", "being", "percent", "speaking", "full", "sentences",
    "can", "could", "hear", "both", "sides", "about", "best", "this", "that", "these", "those",
    "we", "will", "give", "now", "three", "back", "to", "with", "and", "or", "short", "course",
    "of", "for", "days", "okay", "after", "reassess", "use", "start", "again", "every", "day",
    "if", "get", "at", "rest", "come", "immediately", "tell", "me", "happen", "happened",
    "there", "here", "she", "he", "they", "them", "his", "her", "their", "my", "the", "a", "an",
    "from", "by", "in", "on", "into", "onto", "over", "under", "above", "below", "between",
    "so", "then", "very", "much", "more", "some", "all", "also", "well", "feeling", "feels",
}


def tokenize(text: str) -> list[str]:
    tokens = NON_ALPHANUM.split(text.lower())
    return [t for t in tokens if (len(t) > 1 or t.isdigit()) and t not in CONVERSATIONAL_STOPWORDS]


def retrieve_candidates(query_text: str, top_k: int = 20) -> list[dict]:
    idx = load_index()
    bm25: BM25Okapi = idx["bm25"]
    codes = idx["codes"]
    titles = idx["titles"]
    leaves = idx["leaves"]
    residuals = idx["residuals"]
    depths = idx["depths"]
    chapters = idx["chapters"]

    tokens = tokenize(query_text)
    if not tokens:
        tokens = ["unspecified"]

    scores = bm25.get_scores(tokens)

    # Get indices of top_k highest scores
    import numpy as np
    top_indices = np.argsort(scores)[::-1][:top_k]

    candidates = []
    for rank, i in enumerate(top_indices):
        score = float(scores[i])
        candidates.append({
            "code": codes[i],
            "title": titles[i],
            "leaf": leaves[i],
            "residual": residuals[i],
            "depth": depths[i],
            "chapter": chapters[i],
            "bm25_score": score,
            "bm25_rank": rank + 1,
        })

    return candidates
