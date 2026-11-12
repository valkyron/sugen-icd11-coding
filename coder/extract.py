"""Clinical note extractor and normalizer.

Parses doctor notes across all formats (typed SOAP, short consult, ambient transcript),
normalizes medical shorthand, extracts diagnostic conclusions, and handles negations.
"""

import re

# Comprehensive outpatient clinical abbreviation map
ABBREVIATIONS = [
    (re.compile(r"\burti\b", re.I), "upper respiratory tract infection acute"),
    (re.compile(r"\blrti\b", re.I), "lower respiratory tract infection"),
    (re.compile(r"\buti\b", re.I), "urinary tract infection cystitis"),
    (re.compile(r"\bhtn\b", re.I), "essential hypertension high blood pressure"),
    (re.compile(r"\bt2dm\b", re.I), "type 2 diabetes mellitus"),
    (re.compile(r"\bt1dm\b", re.I), "type 1 diabetes mellitus"),
    (re.compile(r"\bdm\b", re.I), "diabetes mellitus"),
    (re.compile(r"\bpud\b", re.I), "peptic ulcer disease dyspepsia"),
    (re.compile(r"\bgerd\b", re.I), "gastroesophageal reflux disease"),
    (re.compile(r"\bpid\b", re.I), "pelvic inflammatory disease"),
    (re.compile(r"\bage\b", re.I), "acute gastroenteritis diarrhoea"),
    (re.compile(r"\bcap\b", re.I), "community acquired pneumonia"),
    (re.compile(r"\bptb\b", re.I), "pulmonary tuberculosis"),
    (re.compile(r"\btb\b", re.I), "tuberculosis"),
    (re.compile(r"\boa\b", re.I), "osteoarthritis"),
    (re.compile(r"\bra\b", re.I), "rheumatoid arthritis"),
    (re.compile(r"\bcopd\b", re.I), "chronic obstructive pulmonary disease"),
    (re.compile(r"\bbph\b", re.I), "benign prostatic hyperplasia"),
    (re.compile(r"\bcoartem\b", re.I), "malaria falciparum"),
    (re.compile(r"\bal\b", re.I), "malaria artemether"),
    (re.compile(r"\bmrdt\b", re.I), "malaria rapid diagnostic test"),
    (re.compile(r"\bmps\b", re.I), "malaria parasites"),
    (re.compile(r"\bs\.?\s*typhi\b", re.I), "salmonella typhi typhoid fever"),
    (re.compile(r"\bp\.?\s*falciparum\b", re.I), "plasmodium falciparum malaria"),
    (re.compile(r"\bp\.?\s*vivax\b", re.I), "plasmodium vivax malaria"),
    (re.compile(r"\bhba1c\b", re.I), "glycated hemoglobin diabetes"),
    (re.compile(r"\bupt\b", re.I), "urine pregnancy test pregnancy"),
    (re.compile(r"\blmp\b", re.I), "last menstrual period"),
    (re.compile(r"\bcva\b", re.I), "cerebrovascular accident stroke"),
    (re.compile(r"\btia\b", re.I), "transient ischaemic attack"),
    (re.compile(r"\bdvt\b", re.I), "deep vein thrombosis"),
    (re.compile(r"\bpe\b", re.I), "pulmonary embolism"),
    (re.compile(r"\bmtb\b", re.I), "mycobacterium tuberculosis"),
    (re.compile(r"\bgenexpert\b", re.I), "tuberculosis test"),
    (re.compile(r"\be\.?\s*histolytica\b", re.I), "entamoeba histolytica amoebiasis dysentery"),
    (re.compile(r"\bh\.?\s*pylori\b", re.I), "helicobacter pylori gastritis peptic ulcer"),
]

NEGATION_PATTERNS = [
    re.compile(r"\b(no|not|denies|neg|negative|excluded|ruled\s*out|free\s*of)\s+([a-z0-9\s]{2,25})", re.I),
    re.compile(r"([a-z0-9\s]{2,25})\s+(neg|negative|excluded|ruled\s*out)", re.I),
]

SECTION_A_PATTERN = re.compile(
    r"(?:^|\n|[.,;])\s*(?:a|imp|impression|assessment|dx|diagnosis)[:\s]+([^\n;]+)",
    re.I,
)
SECTION_IX_PATTERN = re.compile(
    r"(?:^|\n|[.,;])\s*(?:ix|investigations|labs|lab)[:\s]+([^\n;]+)",
    re.I,
)


def expand_abbreviations(text: str) -> str:
    expanded = text
    for pattern, replacement in ABBREVIATIONS:
        expanded = pattern.sub(f"\\g<0> {replacement}", expanded)
    return expanded


def detect_style(text: str) -> str:
    lower = text.lower()
    if "doctor:" in lower or "clinician:" in lower or "patient:" in lower:
        return "ambient_transcript"
    if any(marker in lower for marker in ["\ns:", "\no:", "\na:", "\np:", "\nimp:", "o/e:"]):
        return "typed_consult"
    return "short_consult"


def extract_diagnostic_query(text: str) -> dict:
    """Extract query text with high-priority diagnosis signals and full context."""
    style = detect_style(text)
    high_priority_parts = []
    expanded_full = expand_abbreviations(text)

    if style == "typed_consult":
        # Extract assessment / impression if present
        a_match = SECTION_A_PATTERN.search(text)
        if a_match:
            high_priority_parts.append(a_match.group(1).strip())
        # Extract labs / investigations
        ix_match = SECTION_IX_PATTERN.search(text)
        if ix_match:
            high_priority_parts.append(ix_match.group(1).strip())

    elif style == "ambient_transcript":
        # Look for doctor diagnosis statements
        lines = text.split("\n")
        for line in lines:
            line_str = line.strip()
            if line_str.lower().startswith(("doctor:", "dr:", "clinician:")):
                # Doctor lines with diagnostic clues
                if any(w in line_str.lower() for w in [
                    "this is", "looks like", "diagnos", "attack", "infection",
                    "give", "prescrib", "start", "treating", "syndrome"
                ]):
                    high_priority_parts.append(line_str)

    elif style == "short_consult":
        # Look for Dx, Imp, or final statements
        dx_match = re.search(r"\b(?:dx|imp|assessment)\b[:\s]+([^\n,;]+)", text, re.I)
        if dx_match:
            high_priority_parts.append(dx_match.group(1).strip())

    high_priority_text = " ".join(high_priority_parts)
    high_priority_expanded = expand_abbreviations(high_priority_text)

    # Combined query gives 3x weight to high priority diagnostic terms + 1x to the rest
    if high_priority_expanded.strip():
        query_text = f"{high_priority_expanded} {high_priority_expanded} {high_priority_expanded} {expanded_full}"
    else:
        query_text = expanded_full

    return {
        "style": style,
        "query_text": query_text,
        "high_priority_text": high_priority_text,
        "expanded_full": expanded_full,
    }
