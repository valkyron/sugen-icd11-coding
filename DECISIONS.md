# Architectural & Engineering Decisions Log

### 1. Initial Unpack & Understanding the Brief
* **Date & Time:** 2026-11-11 20:00 UTC | **Commit:** `44d1a6d`
* **Context & Problem:** Extracted `SugenEngTest.tgz`. Analyzed `BRIEF.md`, `mms-2026-01.json`, and `score.py`.
* **Key Observations:**
  - Strict $1.00 total LLM budget across 300 notes (~$0.0033/note) -> eliminates multi-agent loops and heavy zero-shot prompts.
  - Runtime network locked to OpenAI/Anthropic proxies -> all indexes and models must be 100% offline.
  - System must output valid codes even with no API key -> requires a robust local fallback.
  - Laptop lacks Docker -> develop and test in pure Python locally, package Docker files for final submission.

---

### 2. Exploring Solution Approaches & Discarding Traditional Classifiers
* **Date & Time:** 2026-11-11 21:00 UTC | **Commit:** `44d1a6d`
* **Decision:** Treat the problem as **Two-Stage Retrieval + Reranking**, not supervised classification or fine-tuning.
* **Options Considered:**
  1. *Supervised Classifier (e.g. BioBERT / CatBoost)*: ICD-11 has 18,375 classes. 60 dev notes touch only 58 distinct codes across 11 chapters; 18,317 codes have 0 training samples. A classifier cannot predict unseen classes in Slice B.
  2. *Dense Vector Embeddings (HNSW / FAISS)*: Heavy on CPU (500MB+ RAM, 40ms/note), and misses exact lab codes / pathogen species (e.g. *P. falciparum* vs *P. vivax*).
  3. *Lightweight Two-Stage Search*: Enriched local search to narrow 18,375 codes to Top 15 -> cheap LLM reranker (`gpt-4o-mini`) to pick Top 3.

---

### 3. WHO ICD-11 Data Enrichment
* **Date & Time:** 2026-11-12 00:35 UTC | **Commit:** `2a988f2`
* **Decision:** Download and join the official WHO ICD-11 2026-01 Simple Tabulation (`SimpleTabulation-ICD-11-MMS-en.txt`) ahead of time to enrich all 18,375 categories.
* **Why & What Was Added:**
  - `mms-2026-01.json` only had basic titles.
  - WHO tabulation provides 20 columns: disease blocks (e.g., *Bacterial intestinal infections*), 5 levels of clinical groupings, and coding inclusion notes.
  - Clinicians often write disease families or synonyms (e.g. *"enteric fever"*) rather than exact ICD titles (*"Typhoid fever, unspecified"*). Enriched blocks bridge this vocabulary gap offline.

---

### 4. Field-Weighted BM25 Candidate Retriever
* **Date & Time:** 2026-11-12 00:50 UTC | **Commit:** `2a988f2`
* **Decision:** Build an offline BM25Okapi index with field-weighted tokens: Category Title (3x), Groupings & Blocks (2x), Inclusions & Notes (1x), Code (1x).
* **Measured Evidence:**
  - Serialized index is only 4.5 MB on disk, loads in <0.2s, and searches in ~15ms on CPU.
  - Recall test across all 60 dev notes showed **65.0% of notes have the true gold code in the Top 30 retrieved candidates**.

---

### 5. Clinical Preprocessor: Stopwords, Negations & WHO Spellings
* **Date & Time:** 2026-11-12 01:15 UTC | **Commit:** `6746e03`
* **Decision:** Implement `coder/extract.py` to extract SOAP sections (`A:`, `Imp:`, `Dx:`), strip conversational dialogue stopwords from ambient transcripts, filter out negated diagnoses, and map British/WHO medical spellings (*candidosis* vs *candidiasis*, *diarrhoea* vs *diarrhea*).
* **Measured Evidence:**
  - **Negation fix:** In `dev-004`, note said *"Previous malaria was likely misdiagnosis. Blood culture: Salmonella Typhi isolated"*. Naive search repeated "malaria" 15 times (Rank 1-20 malaria). Negation filtering instantly boosted Typhoid (`1A07.Z`) to Rank 1.
  - **Spelling fix:** In `dev-005` (*vaginal thrush*), expanding to WHO British spelling (*candidosis*) jumped `1F23.10` from unranked straight to Rank 1.
  - **Overall dev score:** Rose from **14.2 to 19.2 / 75 points** on `score.py` purely from preprocessor intelligence.

---

### 6. Deterministic Leaf-Promotion Heuristic (Stage 2B Offline Fallback)
* **Date & Time:** 2026-11-12 01:35 UTC | **Commit:** `b0e1560`
* **Decision:** In the no-key fallback ranker, apply deterministic weights: boost terminal leaf codes (`leaf: True`, +35%), penalize non-leaf parent categories (-20%), boost `.Z` unspecified codes (+20%), and automatically promote child codes when both parent and child match.
* **Measured Evidence:**
  - Aligns with the grading rule: *"A parent code does not count when a child fits."*
  - Achieved **0 missing predictions, 0 invalid codes, 0 duplicate IDs**, and a solid **19.2 / 75.0 points** with zero API key and $0.00 spent.

---

### 7. Stage 2A LLM Reranker with Hard Budget Telemetry
* **Date & Time:** 2026-11-12 02:00 UTC | **Commit:** `8736e97` & `8c2efdd`
* **Decision:** Implement LLM reranking using `gpt-4o-mini` (or Claude 3.5 Haiku) with a hard-coded `$0.80` budget ceiling (20% safety buffer below the $1.00 cap) and a 4-second timeout that automatically falls back to Stage 2B.
* **Why:**
  - Sending note + 15 candidates costs ~$0.00006 per note (~$0.02 for all 300 notes).
  - An LLM easily solves clinical nuances BM25 cannot (e.g. recognizing that wheezing + crackles + opacity = acute pneumonia, or selecting knee vs hip osteoarthritis).

---

### 8. Generalisation Suite (Slice B Validation)
* **Date & Time:** 2026-11-12 02:25 UTC | **Commit:** `b317443`
* **Decision:** Build a synthetic validation harness (`tests/eval_generalisation.py`) with 15 clinical consults covering the **15 ICD-11 chapters absent from `dev_notes`** (oncology, hematology, neurology, psychiatry, ophthalmology, ENT, injuries) and multilingual notes (Spanish, French, Swahili code-switching).
* **Measured Evidence:**
  - Running `score.py` on this suite confirmed **6.7 / 25.0 points** in pure offline mode across unseen chapters and languages, verifying that the enriched index does not collapse outside the dev set distribution.

---

### 9. Docker Packaging & Proxy Forwarding
* **Date & Time:** 2026-11-12 02:45 UTC | **Commit:** `5d10ad1`
* **Decision:** Package the solution in `python:3.11-slim` with pre-built BM25 artifacts and enriched data copied directly into `/app`. Set up `docker-compose.yml` to forward `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `HTTPS_PROXY`.
* **Measured Evidence:**
  - Matches the exact grading invocation: `docker compose run coder /in/notes.jsonl /out/predictions.jsonl`.
  - Zero external network downloads needed at runtime. Streams predictions line-by-line with `flush=True`.

---

### 10. Candidate Window Expansion to Top 25
* **Date & Time:** 2026-11-12 03:20 UTC | **Commit:** `89e92e5`
* **Decision:** Expand the candidate retrieval window fed from BM25 into the LLM reranker from Top 15 to Top 25 (`coder/llm_reranker.py` and `coder/main.py`).
* **Options Considered:**
  1. *Fixed Top 15*: Kept prompt size compact (~220 input tokens), but limited recall ceiling to 51.7% because 8 valid diagnoses sat between ranks 16 and 24.
  2. *Top 25*: Increased candidate recall ceiling to 66.7%, exposing valid codes to the LLM without adding hardcoded extraction rules.
  3. *Top 40+*: Introduced excessive distractor codes and diluted prompt attention.
* **Measured Evidence:**
  - Top-1 accuracy rose from 46.7% to **55.0%** (+5 notes correct).
  - Dev score rose from 35.4 to **41.2 / 75.0 points** (+5.8 points).
  - Spend was only **$0.01134** across all 60 notes (~$0.05 estimated for 300 notes), safely utilizing only ~5% of the $1.00 budget.

---

### 11. Outpatient Clinical Syndrome Clusters & Medical Cognates
* **Date & Time:** 2026-11-13 06:00 UTC | **Commit:** `83e69bf`
* **Decision:** Incorporate 12 core clinical syndrome clusters based on WHO primary care standards (pneumonia consolidation, asthma bronchospasm, cystitis/UTI, infectious dysentery, acid-peptic disease, osteoarthritis, migraine) along with Romance/Latin medical cognate mapping (*migrañ-*, *otit-*, *conjonctiv-*, *pneumon-*).
* **Options Considered:**
  1. *Rely purely on keyword tokens*: Misses notes where doctors record physical exam findings (e.g. lung crackles, dysuria) without stating the disease name.
  2. *Overfitted narrow regex*: Brittle and risky for hidden notes.
  3. *Universal medical syndrome clusters & cognates*: Medically sound, standard primary care categories covering 90%+ of outpatient presentations worldwide.
* **Measured Evidence:**
  - Top-1 accuracy surged from 55.0% to **61.7%** (37 / 60 notes correct on first guess).
  - Top-3 accuracy reached **63.3%** (38 / 60 notes).
  - Dev score reached **46.7 / 75.0 points** (+5.5 points).
  - Spend remained low at **$0.01151** across all 60 notes (~$0.05 projected for 300 notes, leaving 95% of the $1.00 budget unspent).
