"""Build enriched ICD-11 MMS index from WHO Simple Tabulation and local mms-2026-01.json."""

import io
import json
import os
import pickle
import re
import urllib.request
import zipfile
from rank_bm25 import BM25Okapi

WHO_TABULATION_URL = "https://icdcdn.who.int/static/releasefiles/2026-01/SimpleTabulation-ICD-11-MMS-en.zip"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MMS_JSON_PATH = os.path.join(BASE_DIR, "data", "mms-2026-01.json")
ENRICHED_JSON_PATH = os.path.join(BASE_DIR, "coder", "data", "enriched_mms.json")
BM25_INDEX_PATH = os.path.join(BASE_DIR, "coder", "data", "bm25_index.pkl")

STEM_SPLIT = re.compile(r"[&/]")
DASH_PREFIX = re.compile(r"^[\s\"'-]+|[\s\"']+$")
NON_ALPHANUM = re.compile(r"[^a-z0-9]+")


def norm_code(code: str) -> str:
    if not code:
        return ""
    return STEM_SPLIT.split(code.strip())[0].strip().upper()


def clean_title(title: str) -> str:
    if not title:
        return ""
    t = DASH_PREFIX.sub("", title.strip())
    t = DASH_PREFIX.sub("", t)
    return t.strip()


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = NON_ALPHANUM.split(text)
    return [t for t in tokens if len(t) > 1 or t.isdigit()]


def download_who_tabulation() -> io.BytesIO:
    print(f"Downloading WHO Simple Tabulation from {WHO_TABULATION_URL}...")
    req = urllib.request.Request(WHO_TABULATION_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read()
    print(f"Downloaded {len(content):,} bytes.")
    return io.BytesIO(content)


def build_enriched_index():
    with open(MMS_JSON_PATH, encoding="utf-8") as f:
        mms_raw = json.load(f)

    valid_codes = {norm_code(r["code"]): r for r in mms_raw}
    print(f"Loaded {len(valid_codes)} valid categories from {MMS_JSON_PATH}")

    zip_bytes = download_who_tabulation()
    who_table = {}
    block_titles = {}
    uri_titles = {}

    with zipfile.ZipFile(zip_bytes) as zf:
        with zf.open("SimpleTabulation-ICD-11-MMS-en.txt") as f:
            header_line = f.readline().decode("utf-8-sig").rstrip("\r\n")
            cols = header_line.split("\t")
            col_map = {name: idx for idx, name in enumerate(cols)}

            def get_val(row_parts, name, default=""):
                idx = col_map.get(name)
                if idx is not None and idx < len(row_parts):
                    return row_parts[idx].strip()
                return default

            for line in f:
                parts = line.decode("utf-8-sig", errors="ignore").rstrip("\r\n").split("\t")

                foundation_uri = get_val(parts, "Foundation URI")
                code = norm_code(get_val(parts, "Code"))
                block_id = get_val(parts, "BlockId")
                title = clean_title(get_val(parts, "Title"))
                coding_note = get_val(parts, "CodingNote")
                groupings = [get_val(parts, f"Grouping{i}") for i in range(1, 6)]
                parent = get_val(parts, "Parent")

                if block_id and title:
                    block_titles[block_id] = title
                if foundation_uri and title:
                    uri_titles[foundation_uri] = title

                if code:
                    who_table[code] = {
                        "block_id": block_id,
                        "raw_title": title,
                        "groupings": [g for g in groupings if g],
                        "coding_note": coding_note if not coding_note.startswith("http") else "",
                        "parent": parent,
                    }

    print(f"Parsed {len(who_table)} entries and {len(block_titles)} blocks from WHO table.")

    enriched_records = []
    corpus_tokens = []

    for item in mms_raw:
        c = norm_code(item["code"])
        title = item.get("title", "")
        leaf = bool(item.get("leaf", False))
        residual = bool(item.get("residual", False))
        depth = int(item.get("depth", 1))
        chapter = item.get("chapter", "")

        who_info = who_table.get(c, {})
        grouping_blocks = who_info.get("groupings", [])
        grouping_names = [block_titles[g] for g in grouping_blocks if g in block_titles]

        coding_note = who_info.get("coding_note", "")
        block_id = who_info.get("block_id", "")
        block_name = block_titles.get(block_id, "")

        parent_ref = who_info.get("parent", "")
        parent_name = uri_titles.get(parent_ref, "") or block_titles.get(parent_ref, "")

        # Field-weighted search text
        # Title 3x, Block/Groupings 2x, Notes 1x, Code 1x
        search_parts = [
            title,
            title,
            title,
            c,
        ]
        if block_name:
            search_parts.extend([block_name, block_name])
        for g_name in grouping_names:
            search_parts.extend([g_name, g_name])
        if parent_name and parent_name not in grouping_names:
            search_parts.append(parent_name)
        if coding_note:
            search_parts.append(coding_note)

        combined_search_text = " ".join(search_parts)
        tokens = tokenize(combined_search_text)

        rec = {
            "code": c,
            "title": title,
            "leaf": leaf,
            "residual": residual,
            "depth": depth,
            "chapter": chapter,
            "block_id": block_id,
            "block_name": block_name,
            "groupings": grouping_names,
            "coding_note": coding_note,
            "search_text": combined_search_text,
        }
        enriched_records.append(rec)
        corpus_tokens.append(tokens)

    os.makedirs(os.path.dirname(ENRICHED_JSON_PATH), exist_ok=True)
    with open(ENRICHED_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(enriched_records, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(enriched_records)} enriched records to {ENRICHED_JSON_PATH}")

    print("Fitting BM25Okapi index...")
    bm25 = BM25Okapi(corpus_tokens)

    index_payload = {
        "bm25": bm25,
        "codes": [r["code"] for r in enriched_records],
        "titles": [r["title"] for r in enriched_records],
        "leaves": [r["leaf"] for r in enriched_records],
        "residuals": [r["residual"] for r in enriched_records],
        "depths": [r["depth"] for r in enriched_records],
        "chapters": [r["chapter"] for r in enriched_records],
    }

    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(index_payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Saved serialized BM25 index to {BM25_INDEX_PATH} ({os.path.getsize(BM25_INDEX_PATH):,} bytes).")


if __name__ == "__main__":
    build_enriched_index()
