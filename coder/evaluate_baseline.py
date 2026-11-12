"""Evaluate pure offline baseline on dev_notes.jsonl."""

import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from coder.extract import extract_diagnostic_query
from coder.retrieve import retrieve_candidates
from coder.local_ranker import rank_local_candidates
DEV_NOTES_PATH = os.path.join(BASE_DIR, "data", "dev_notes.jsonl")
OUT_DIR = os.path.join(BASE_DIR, "out")
PRED_PATH = os.path.join(OUT_DIR, "baseline_predictions.jsonl")
SCORE_SCRIPT = os.path.join(BASE_DIR, "score.py")
MMS_PATH = os.path.join(BASE_DIR, "data", "mms-2026-01.json")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    notes = []
    with open(DEV_NOTES_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                notes.append(json.loads(line))

    print(f"Running pure offline baseline on {len(notes)} notes...")
    with open(PRED_PATH, "w", encoding="utf-8") as out_f:
        for note in notes:
            nid = note["id"]
            text = note["text"]
            extracted = extract_diagnostic_query(text)
            candidates = retrieve_candidates(extracted["query_text"], top_k=20)
            pred_codes = rank_local_candidates(candidates, extracted)

            out_f.write(json.dumps({"id": nid, "codes": pred_codes}) + "\n")

    print(f"Predictions written to {PRED_PATH}")
    print("\n--- Running score.py ---")
    cmd = [
        sys.executable,
        SCORE_SCRIPT,
        "--gold",
        DEV_NOTES_PATH,
        "--pred",
        PRED_PATH,
        "--mms",
        MMS_PATH,
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
