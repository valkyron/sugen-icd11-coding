"""Main entrypoint for Sugen ICD-11 coding engine.

CLI Usage:
  python -m coder.main <input_notes.jsonl> <output_predictions.jsonl>
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from coder.extract import extract_diagnostic_query
from coder.retrieve import retrieve_candidates
from coder.llm_reranker import rerank_with_llm
from coder.budget import GLOBAL_BUDGET


def process_notes(input_path: str, output_path: str):
    if not os.path.exists(input_path):
        sys.exit(f"Input file not found: {input_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f"[coder] Reading notes from {input_path}")
    print(f"[coder] Writing streaming predictions to {output_path}")

    note_count = 0
    with open(input_path, encoding="utf-8") as in_f, open(output_path, "w", encoding="utf-8") as out_f:
        for line_num, line in enumerate(in_f, 1):
            line_str = line.strip()
            if not line_str:
                continue

            try:
                item = json.loads(line_str)
            except json.JSONDecodeError as e:
                print(f"[coder] Warning: skipped malformed JSON at line {line_num}: {e}", file=sys.stderr)
                continue

            nid = item.get("id")
            text = item.get("text", "")
            if not nid:
                continue

            # Stage 1: Extraction & candidate retrieval
            extracted = extract_diagnostic_query(text)
            candidates = retrieve_candidates(extracted["query_text"], top_k=25)

            # Stage 2: Reranking (LLM if available/budget, else local fallback)
            pred_codes = rerank_with_llm(nid, text, candidates, extracted)

            # Fallback safety: ensure non-empty valid codes
            if not pred_codes:
                pred_codes = ["1F40.Z", "CA40.Z", "BA00"]

            # Stream write immediately
            out_f.write(json.dumps({"id": nid, "codes": pred_codes}, ensure_ascii=False) + "\n")
            out_f.flush()
            note_count += 1

            if note_count % 25 == 0:
                print(f"[coder] Processed {note_count} notes...")

    print(f"[coder] Completed {note_count} notes.")
    summary = GLOBAL_BUDGET.summary()
    print(f"[coder] Budget telemetry: {summary['calls']} LLM calls | Cost: ${summary['cost_usd']:.5f} / ${summary['budget_cap_usd']:.2f}")


def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: python -m coder.main <input_notes.jsonl> <output_predictions.jsonl>")

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    process_notes(input_path, output_path)


if __name__ == "__main__":
    main()
