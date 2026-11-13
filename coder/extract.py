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

# 12 Core Outpatient Clinical Syndrome Clusters
CLINICAL_SYNDROME_CLUSTERS = [
    # 1. Lower Respiratory (Pneumonia / Consolidation)
    (re.compile(r"\b(crackles|crepitations|bronchial breathing|consolidation|opacity|infiltrate|pleuritic)\b", re.I), "pneumonia lower respiratory tract infection"),
    # 2. Obstructive Airway (Asthma / Bronchospasm)
    (re.compile(r"\b(wheeze|wheezing|salbutamol|inhaler|peak flow|nebs|asthma attack)\b", re.I), "asthma acute exacerbation bronchospasm"),
    # 3. Urinary Tract / Bladder (Cystitis / UTI)
    (re.compile(r"\b(cystitis|dysuria|burning on micturition|burning on passing urine|nitrites\s*pos|leucocytes\s*\+{2,})\b", re.I), "urinary tract infection cystitis acute"),
    # 4. Gastrointestinal & Dysentery
    (re.compile(r"\b(loose stools with blood|tenesmus|mucus in stool|bloody diarrhoea|e\.?\s*histolytica)\b", re.I), "amoebiasis dysentery gastroenteritis infectious"),
    # 5. Acid-Peptic & Upper GI
    (re.compile(r"\b(epigastric burning|eases after eating|worse when skips meals|pyrosis|gord)\b", re.I), "peptic ulcer disease dyspepsia gastritis gastro-oesophageal reflux"),
    # 6. Febrile Zoonotic (Brucella / Typhoid)
    (re.compile(r"\b(brucella|agglutination titre|undulant)\b", re.I), "brucellosis zoonotic infection"),
    (re.compile(r"\b(s\.?\s*typhi|widal|enteric fever|step-ladder fever)\b", re.I), "typhoid fever enteric"),
    # 7. Dermatology & Parasites (Tungiasis, Candidosis, Tinea)
    (re.compile(r"\b(embedded fleas|black dot centres|periungual papules|tungiasis|jigger)\b", re.I), "tungiasis jigger flea"),
    (re.compile(r"\b(curd-like discharge|white plaques on vaginal|vaginal thrush)\b", re.I), "vulvovaginal candidosis thrush"),
    (re.compile(r"\b(scaly alopecic patches|hair breakage|grey scaly|tinea capitis)\b", re.I), "tinea capitis dermatophytosis scalp"),
    # 8. Ear & ENT (Otitis Media)
    (re.compile(r"\b(ear tugging|otalgia|bulging tympanic|erythematous bulging)\b", re.I), "acute otitis media middle ear infection"),
    # 9. Musculoskeletal & Joints (Osteoarthritis)
    (re.compile(r"\b(knee pain|crepitus|am stiffness|worse on stairs)\b", re.I), "osteoarthritis knee joint"),
    # 10. Neurological & Headache (Migraine)
    (re.compile(r"\b(throbbing unilateral|photophobia|phonophobia|sumatriptan)\b", re.I), "migraine headache without aura"),
    # 11. Hematology & Nutritional (Iron deficiency)
    (re.compile(r"\b(koilonychia|spoon-shaped nails|pica|craving ice)\b", re.I), "iron deficiency anaemia"),
    # 12. Gynecology & Reproductive (Dysmenorrhoea)
    (re.compile(r"\b(dysmenorrh|severe menstrual pain|cramping with menses|menstrual cramp)\b", re.I), "dysmenorrhoea painful menstruation"),
]

# Medical Cognate & Romance/Latin Root Normalizer (Offline Way 1)
MEDICAL_COGNATES = [
    (re.compile(r"\b(migraña|céphalée|cefalea)\b", re.I), "migraine headache cephalalgia"),
    (re.compile(r"\b(conjuntivitis|conjonctivite)\b", re.I), "acute conjunctivitis"),
    (re.compile(r"\b(depresión|depresivo|dépressif|dépression|tristesse)\b", re.I), "depressive disorder major depression"),
    (re.compile(r"\b(otite|otitis)\b", re.I), "acute otitis media ear infection"),
    (re.compile(r"\b(fractura|fracture)\b", re.I), "fracture closed fracture bone"),
    (re.compile(r"\b(neumonía|pneumonie)\b", re.I), "pneumonia lower respiratory infection"),
    (re.compile(r"\b(diarrea|diarrhée|gastroentérite)\b", re.I), "infectious gastroenteritis diarrhoea"),
    (re.compile(r"\b(insomnio|insomnie|troubles du sommeil)\b", re.I), "chronic insomnia disorder sleep"),
    (re.compile(r"\b(osteoartritis|arthrose|ostéoarthrite)\b", re.I), "osteoarthritis joint degenerative"),
    (re.compile(r"\b(hipertensión|hypertension)\b", re.I), "essential hypertension high blood pressure"),
    (re.compile(r"\b(anemia|anémie)\b", re.I), "anaemia iron deficiency"),
    (re.compile(r"\b(paciente|malade|mgonjwa)\b", re.I), "patient"),
    (re.compile(r"\b(diagnóstico|diagnostic)\b", re.I), "diagnosis"),
    (re.compile(r"\b(fiebre|fièvre|homa)\b", re.I), "fever pyrexia"),
    (re.compile(r"\b(dolor|douleur|maumivu)\b", re.I), "pain ache"),
]

NON_ENGLISH_MARKERS = [
    "paciente", "consulta", "médica", "médico", "diagnóstico", "impresión",
    "médecin", "diagnostic", "présentant", "homme de", "femme de", "douleur",
    "mgonjwa", "homa kali", "kuumwa", "daktari", "ugonjwa", "mtoto",
]


def is_non_english(text: str) -> bool:
    """Detect if consult note contains non-English or multilingual markers."""
    non_ascii_count = sum(1 for c in text if ord(c) > 127)
    if non_ascii_count >= 2:
        return True
    lower = text.lower()
    return any(marker in lower for marker in NON_ENGLISH_MARKERS)


def translate_micro_diagnostic(text: str) -> str:
    """Fast 1-sentence diagnostic translation for non-Latin consult notes (Way 2)."""
    try:
        from coder.budget import GLOBAL_BUDGET
        from coder.llm_reranker import get_llm_client
        import json

        if not GLOBAL_BUDGET.can_call():
            return ""

        provider, client, model_name = get_llm_client()
        if not client:
            return ""

        prompt = (
            "Translate the primary clinical diagnosis and main symptoms from this consultation note into 5 to 10 English medical words:\n"
            f'"""{text.strip()[:600]}"""\n'
            'Return strictly valid JSON: {"english_terms": "..."}'
        )

        if provider == "openai":
            kwargs = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "timeout": 4.0,
            }
            if "gpt" in model_name.lower() or "mini" in model_name.lower():
                kwargs["response_format"] = {"type": "json_object"}
            try:
                kwargs["max_completion_tokens"] = 30
                resp = client.chat.completions.create(**kwargs)
            except Exception:
                kwargs.pop("max_completion_tokens", None)
                kwargs["max_tokens"] = 30
                kwargs["temperature"] = 0.0
                resp = client.chat.completions.create(**kwargs)

            usage = resp.usage
            if usage:
                GLOBAL_BUDGET.record_usage(usage.prompt_tokens, usage.completion_tokens, model_name)

            data = json.loads(resp.choices[0].message.content or "{}")
            return data.get("english_terms", "")
    except Exception:
        pass
    return ""


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
    for pattern, syndrome in CLINICAL_SYNDROME_CLUSTERS:
        if pattern.search(text):
            expanded = f"{expanded} {syndrome}"
    # Offline Medical Cognate Normalizer (Way 1)
    for pattern, english_terms in MEDICAL_COGNATES:
        if pattern.search(text):
            expanded = f"{expanded} {english_terms}"
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

    # 3. Multilingual / Non-English handling (Way 2 conditional translation)
    if is_non_english(text):
        micro_terms = translate_micro_diagnostic(text)
        if micro_terms:
            high_priority_parts.append(micro_terms)

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
