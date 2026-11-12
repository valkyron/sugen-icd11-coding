"""Clinical note extractor and normalizer with negation awareness."""

import re

# Outpatient clinical abbreviations with context expansions
ABBREVIATIONS = [
    (re.compile(r"\burti\b", re.I), "upper respiratory tract infection"),
    (re.compile(r"\blrti\b", re.I), "lower respiratory tract infection"),
    (re.compile(r"\buti\b", re.I), "urinary tract infection cystitis"),
    (re.compile(r"\bhtn\b", re.I), "essential hypertension high blood pressure"),
    (re.compile(r"\bt2dm\b", re.I), "type 2 diabetes mellitus"),
    (re.compile(r"\bt1dm\b", re.I), "type 1 diabetes mellitus"),
    (re.compile(r"\bdm\b", re.I), "diabetes mellitus"),
    (re.compile(r"\bpud\b", re.I), "peptic ulcer disease dyspepsia"),
    (re.compile(r"\bgerd\b", re.I), "gastro-oesophageal reflux disease"),
    (re.compile(r"\bpid\b", re.I), "pelvic inflammatory disease"),
    (re.compile(r"\bage\b", re.I), "acute gastroenteritis diarrhoea"),
    (re.compile(r"\bcap\b", re.I), "community acquired pneumonia"),
    (re.compile(r"\bptb\b", re.I), "pulmonary tuberculosis"),
    (re.compile(r"\btb\b", re.I), "tuberculosis"),
    (re.compile(r"\boa\b", re.I), "osteoarthritis"),
    (re.compile(r"\bra\b", re.I), "rheumatoid arthritis"),
    (re.compile(r"\bcopd\b", re.I), "chronic obstructive pulmonary disease"),
    (re.compile(r"\bbph\b", re.I), "benign prostatic hyperplasia"),
    (re.compile(r"\bmrdt\b", re.I), "malaria test"),
    (re.compile(r"\bmps\b", re.I), "malaria parasites"),
    (re.compile(r"\bs\.?\s*typhi\b", re.I), "salmonella typhi typhoid fever"),
    (re.compile(r"\bp\.?\s*falciparum\b", re.I), "plasmodium falciparum malaria"),
    (re.compile(r"\bp\.?\s*vivax\b", re.I), "plasmodium vivax malaria"),
    (re.compile(r"\bhba1c\b", re.I), "glycated hemoglobin diabetes"),
    (re.compile(r"\bupt\b", re.I), "urine pregnancy test"),
    (re.compile(r"\blmp\b", re.I), "last menstrual period"),
    (re.compile(r"\bcva\b", re.I), "cerebrovascular accident stroke"),
    (re.compile(r"\btia\b", re.I), "transient ischaemic attack"),
    (re.compile(r"\bdvt\b", re.I), "deep vein thrombosis"),
    (re.compile(r"\bmtb\b", re.I), "mycobacterium tuberculosis"),
    (re.compile(r"\bgenexpert\b", re.I), "tuberculosis test"),
    (re.compile(r"\be\.?\s*histolytica\b", re.I), "entamoeba histolytica amoebiasis dysentery"),
    (re.compile(r"\bh\.?\s*pylori\b", re.I), "helicobacter pylori gastritis peptic ulcer"),
    (re.compile(r"\bthrush\b", re.I), "vulvovaginal candidosis monilia"),
    (re.compile(r"\bcandidiasis\b", re.I), "candidosis"),
    (re.compile(r"\bchickenpox\b", re.I), "varicella"),
    (re.compile(r"\bjigger\b", re.I), "tungiasis flea"),
    (re.compile(r"\bmumps\b", re.I), "parotitis infectious mumps"),
    (re.compile(r"\bhives\b", re.I), "urticaria wheals"),
    (re.compile(r"\bshingles\b", re.I), "herpes zoster"),
    (re.compile(r"\bcold sore\b", re.I), "herpes simplex"),
    (re.compile(r"\bscabies\b", re.I), "scabies sarcoptes"),
    (re.compile(r"\bheartburn\b", re.I), "gastro-oesophageal reflux pyrosis"),
    (re.compile(r"\bdiarrhea\b", re.I), "diarrhoea"),
    (re.compile(r"\bdysmenorrhea\b", re.I), "dysmenorrhoea"),
    (re.compile(r"\besophageal\b", re.I), "oesophageal"),
    (re.compile(r"\besophagus\b", re.I), "oesophagus"),
    (re.compile(r"\bedema\b", re.I), "oedema"),
    (re.compile(r"\banemia\b", re.I), "anaemia"),
    (re.compile(r"\bhemorrhage\b", re.I), "haemorrhage"),
    (re.compile(r"\bfecal\b", re.I), "faecal"),
    (re.compile(r"\bwhiplash\b", re.I), "cervical sprain strain"),
    (re.compile(r"\bsprain\b", re.I), "sprain joint ligament"),
    (re.compile(r"\bflu\b", re.I), "influenza"),
    (re.compile(r"\bstrep\b", re.I), "streptococcal pharyngitis"),
    (re.compile(r"\btonsillitis\b", re.I), "acute tonsillitis pharyngitis"),
]

NEGATION_PATTERNS = [
    re.compile(r"\b(?:no|not|denies|neg|negative|excluded|ruled\s*out|free\s*of|misdiagnosis)\b", re.I),
]

# Patterns for explicit diagnosis markers
DIAGNOSIS_PATTERNS = [
    re.compile(r"(?:^|\n|[.,;])\s*(?:a|imp|impression|assessment|dx|diagnosis)[:\s]+([^\n;]+)", re.I),
    re.compile(r"(?:^|\n|[.,;])\s*(?:ix|investigations|labs|lab)[:\s]+([^\n;]+)", re.I),
    re.compile(r"(?:^|\n|[.,;])\s*(?:c/o|complains of|chief complaint)[:\s]+([^\n;]+)", re.I),
]


def expand_abbreviations(text: str) -> str:
    expanded = text
    for pattern, replacement in ABBREVIATIONS:
        expanded = pattern.sub(f"\\g<0> {replacement}", expanded)
    return expanded


def filter_negations(text: str) -> str:
    """Filter out clauses that describe negative or excluded diagnoses."""
    sentences = re.split(r"[.\n;]", text)
    cleaned_sentences = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        # If the sentence mentions exclusion or negative test, don't include it in high priority
        if any(neg.search(s_clean) for neg in NEGATION_PATTERNS):
            # If it also contains "dx" like "mrdt neg, dx viral urti", keep only the dx part
            dx_m = re.search(r"\b(?:dx|imp|assessment)\b[:\s]+(.*)", s_clean, re.I)
            if dx_m:
                cleaned_sentences.append(dx_m.group(1).strip())
            continue
        cleaned_sentences.append(s_clean)
    return " ".join(cleaned_sentences)


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

    # 1. Look for explicit diagnosis lines
    for pat in DIAGNOSIS_PATTERNS:
        for match in pat.finditer(text):
            clause = match.group(1).strip()
            # Filter obvious negations from diagnosis clause
            if not any(neg.search(clause) for neg in NEGATION_PATTERNS):
                high_priority_parts.append(clause)

    # 2. Ambient transcripts: extract doctor diagnosis & treatment utterances
    if style == "ambient_transcript":
        lines = text.split("\n")
        for line in lines:
            line_str = line.strip()
            if line_str.lower().startswith(("doctor:", "dr:", "clinician:")):
                lower_l = line_str.lower()
                if any(w in lower_l for w in [
                    "this is", "looks like", "diagnos", "attack", "infection",
                    "give", "prescrib", "treating", "syndrome", "acute"
                ]):
                    if not any(neg.search(line_str) for neg in NEGATION_PATTERNS):
                        high_priority_parts.append(line_str)

    high_priority_str = filter_negations(" ".join(high_priority_parts))
    high_priority_expanded = expand_abbreviations(high_priority_str)
    full_positive = filter_negations(text)
    full_expanded = expand_abbreviations(full_positive)

    if high_priority_expanded.strip():
        # Repeat high priority terms 4x for strong relevance boost
        query_text = f"{high_priority_expanded} {high_priority_expanded} {high_priority_expanded} {high_priority_expanded} {full_expanded}"
    else:
        query_text = full_expanded

    return {
        "style": style,
        "query_text": query_text,
        "high_priority_text": high_priority_str,
        "expanded_full": full_expanded,
    }
