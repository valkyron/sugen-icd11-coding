"""Generalisation & Multilingual Validation Suite (Slice B).

Evaluates the coding pipeline across ICD-11 chapters missing from dev_notes (oncology,
hematology, neurology, psychiatry, ophthalmology, ENT, injuries, etc.) and non-English consultations.
"""

import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from coder.main import process_notes
from coder.postprocess import norm_code

GENERALISATION_NOTES = [
    # Chapter 02: Neoplasms
    {
        "id": "gen-ch02-01",
        "text": "64M farmer with a persistent pearly telangiectatic papule on right cheek x6 months, rolled borders, central ulceration. Biopsy confirms basal cell carcinoma. Scheduled for wide local excision.",
        "gold": ["2C61.Z"],
        "slice": "B",
    },
    # Chapter 03: Blood diseases
    {
        "id": "gen-ch03-01",
        "text": "22F presents with severe fatigue, pallor, pica (craving ice), and brittle spoon-shaped nails (koilonychia). Hb 7.8 g/dL, MCV 68 fL, serum ferritin 4 ng/mL. Diagnosis: Iron deficiency anaemia.",
        "gold": ["3A00"],
        "slice": "B",
    },
    # Chapter 06: Mental & behavioural disorders
    {
        "id": "gen-ch06-01",
        "text": "35F c/o low mood, loss of interest in activities, insomnia, crying spells, and worthlessness for 5 weeks following job loss. No psychosis or mania. PHQ-9 score 18. Diagnosis: Major depressive episode, single episode.",
        "gold": ["6A70.Z"],
        "slice": "B",
    },
    # Chapter 07: Sleep-wake disorders
    {
        "id": "gen-ch07-01",
        "text": "40M reporting difficulty initiating and maintaining sleep x4 months, waking unrefreshed, impairing daytime functioning. Tried sleep hygiene without benefit. Dx chronic insomnia disorder.",
        "gold": ["7A00"],
        "slice": "B",
    },
    # Chapter 08: Nervous system
    {
        "id": "gen-ch08-01",
        "text": "29F software engineer with recurrent throbbing unilateral right-sided headache x1 year, accompanied by photophobia, phonophobia, and nausea. No aura. Responds well to sumatriptan. Dx migraine without aura.",
        "gold": ["8A80.0"],
        "slice": "B",
    },
    # Chapter 09: Visual system / Eye
    {
        "id": "gen-ch09-01",
        "text": "16M with red swollen right eye x2 days, gritty sensation, watery discharge and mild morning crusting. Vision intact, cornea clear. Dx acute follicular conjunctivitis.",
        "gold": ["9A60.0"],
        "slice": "B",
    },
    # Chapter 10: Ear & Mastoid
    {
        "id": "gen-ch10-01",
        "text": "4yo brought with sudden right ear tugging, severe otalgia, irritability, and fever T 38.8 C following a cold. Otoscopy: erythematous bulging right tympanic membrane with decreased mobility. Dx acute otitis media.",
        "gold": ["AA80.0"],
        "slice": "B",
    },
    # Chapter 17: Sexual health
    {
        "id": "gen-ch17-01",
        "text": "58M known diabetic reporting inability to achieve and maintain penile erection sufficient for sexual intercourse x8 months. Normal morning erections absent. Dx erectile dysfunction.",
        "gold": ["HA00"],
        "slice": "B",
    },
    # Chapter 21: Symptoms & findings
    {
        "id": "gen-ch21-01",
        "text": "50F presents with generalized enlarged, non-tender rubbery lymph nodes in cervical, axillary, and inguinal regions x3 months with low-grade fever. Labs pending biopsy. Imp: Generalized lymphadenopathy.",
        "gold": ["MD81"],
        "slice": "B",
    },
    # Chapter 22: Injury / Orthopedics
    {
        "id": "gen-ch22-01",
        "text": "17M slipped while playing football, landed on outstretched hand (FOOSH). Immediate wrist pain, swelling, 'dinner fork' deformity. X-ray: Closed fracture of distal radius. Cast applied.",
        "gold": ["NC72.2"],
        "slice": "B",
    },
    # Multilingual: Spanish (Migraine)
    {
        "id": "gen-es-01",
        "text": "Consulta médica: Paciente femenino de 30 años refiere cefalea intensa unilateral y pulsátil de 24 horas de evolución, acompañada de náuseas, vómitos, fotofobia y fonofobia. Sin aura visual. Impresión diagnóstica: Migraña sin aura.",
        "gold": ["8A80.0"],
        "slice": "B",
    },
    # Multilingual: Spanish (Acute conjunctivitis)
    {
        "id": "gen-es-02",
        "text": "Paciente de 25 años consulta por ojo rojo bilateral, secreción purulenta y ardor de tres días de evolución. Agudeza visual conservada. Diagnóstico: Conjuntivitis bacteriana aguda.",
        "gold": ["9A60.0"],
        "slice": "B",
    },
    # Multilingual: French (Depression)
    {
        "id": "gen-fr-01",
        "text": "Consultation générale: Homme de 42 ans se plaignant d'une grande tristesse, anhédonie, fatigue intense et troubles du sommeil depuis plus d'un mois. Diagnostic: Épisode dépressif majeur.",
        "gold": ["6A70.Z"],
        "slice": "B",
    },
    # Multilingual: French (Otitis media)
    {
        "id": "gen-fr-02",
        "text": "Enfant de 5 ans présentant une otalgie aiguë droite avec fièvre à 39C et tympan rouge bombé. Diagnostic clinique: Otite moyenne aiguë.",
        "gold": ["AA80.0"],
        "slice": "B",
    },
    # Multilingual: Swahili / English code-switching (Malaria / Fever)
    {
        "id": "gen-sw-01",
        "text": "Mgonjwa ana homa kali, kuumwa na kichwa na kutetemeka mwili mzima x3 days. BS positive for Plasmodium falciparum trophozoites. Dx uncomplicated falciparum malaria.",
        "gold": ["1F40.Z"],
        "slice": "B",
    },
]


def run_evaluation():
    test_dir = os.path.join(BASE_DIR, "out", "gen_eval")
    os.makedirs(test_dir, exist_ok=True)

    gold_path = os.path.join(test_dir, "gen_gold.jsonl")
    pred_path = os.path.join(test_dir, "gen_pred.jsonl")
    in_notes_path = os.path.join(test_dir, "gen_in.jsonl")

    # Write test gold and input files
    with open(gold_path, "w", encoding="utf-8") as g_f, open(in_notes_path, "w", encoding="utf-8") as in_f:
        for row in GENERALISATION_NOTES:
            g_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            in_f.write(json.dumps({"id": row["id"], "text": row["text"]}, ensure_ascii=False) + "\n")

    # Run coder
    process_notes(in_notes_path, pred_path)

    # Score with score.py
    mms_path = os.path.join(BASE_DIR, "data", "mms-2026-01.json")
    cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "score.py"),
        "--gold",
        gold_path,
        "--pred",
        pred_path,
        "--mms",
        mms_path,
    ]
    print("\n--- Generalisation Evaluation Score ---")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    run_evaluation()
