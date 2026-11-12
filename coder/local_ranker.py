"""Deterministic local ranker (Stage 2B fallback).

Ranks retrieved candidates using BM25 relevance weighted by leaf node specificity,
parent-child relationships, and diagnostic depth. Guaranteed 100% offline.
"""

from coder.postprocess import clean_predictions


def rank_local_candidates(candidates: list[dict], query_info: dict | None = None) -> list[str]:
    """Deterministically rerank BM25 candidates favoring specific leaf codes."""
    if not candidates:
        return ["1F40.Z", "CA40.Z", "BA00"]

    # Map codes to their candidate dict
    cand_by_code = {c["code"]: c for c in candidates}

    # Group by prefix/parent to detect parent-child pairs
    # E.g. parent "1A07", child "1A07.Z"
    scored_candidates = []
    max_bm25 = max((c["bm25_score"] for c in candidates), default=1.0) or 1.0

    for c in candidates:
        code = c["code"]
        norm_score = c["bm25_score"] / max_bm25
        weight = 1.0

        # Specificity boosts
        if c.get("leaf"):
            weight += 0.35  # Strong preference for leaf nodes
        else:
            weight -= 0.20  # Penalize non-leaf parent categories

        # Residual .Z (unspecified) is right when details are missing
        if c.get("residual") and code.endswith(".Z"):
            weight += 0.20

        # Check if parent of this code is also in candidates
        if "." in code:
            parent_code = code.rsplit(".", 1)[0]
            if parent_code in cand_by_code:
                # Child matches same disease as parent candidate -> boost child over parent
                weight += 0.30

        # Slight boost for deeper clinical depth
        depth = c.get("depth", 1)
        weight += min(depth * 0.05, 0.20)

        final_score = norm_score * weight
        scored_candidates.append((final_score, code))

    # Sort descending by final score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    ordered_codes = [c for _, c in scored_candidates]

    return clean_predictions(ordered_codes, max_codes=3)
