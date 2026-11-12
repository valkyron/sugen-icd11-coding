"""Post-processing and validation against valid MMS categories."""

import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MMS_JSON_PATH = os.path.join(BASE_DIR, "data", "mms-2026-01.json")
STEM_SPLIT = re.compile(r"[&/]")

_VALID_CODES_CACHE = None


def norm_code(code: str) -> str | None:
    if not isinstance(code, str):
        return None
    stem = STEM_SPLIT.split(code.strip())[0].strip().upper()
    return stem or None


def get_valid_codes() -> set[str]:
    global _VALID_CODES_CACHE
    if _VALID_CODES_CACHE is None:
        with open(MMS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _VALID_CODES_CACHE = {norm_code(r["code"]) for r in data if r.get("code")}
    return _VALID_CODES_CACHE


def clean_predictions(codes: list[str], max_codes: int = 3) -> list[str]:
    """Filter, normalize, and deduplicate predicted codes against MMS categories."""
    valid_set = get_valid_codes()
    cleaned = []
    seen = set()

    for c in codes:
        n = norm_code(c)
        if n and n in valid_set and n not in seen:
            seen.add(n)
            cleaned.append(n)
            if len(cleaned) >= max_codes:
                break

    return cleaned
