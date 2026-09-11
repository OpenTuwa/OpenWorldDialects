# OpenWorldDialects: An Open Research Corpus for World Dialects, Language Variation, and Low-Resource Linguistics

OpenWorldDialects is an open, in-progress research repository for the systematic documentation of **world dialects, regional language varieties, dialectal variation, verb morphology, and conversational grammar** that are underrepresented in mainstream linguistic datasets and natural language processing (NLP) resources.

This project builds **open dialect databases, dialect dictionaries, morphological paradigms, conjugation tables, and cross-dialectal parallel corpora** for use by **linguists, dialectologists, language researchers, computational linguists, NLP engineers, low-resource language developers, and language documentation projects**.

The repository is **actively expanding**. Current data covers initial language families including Sinitic (Mandarin Chinese), Semitic / Arabic dialect continuum (MENA), Austronesian / Malayic varieties (Austronesia), Indo-Aryan / Hindi varieties (India), and Romance (Spanish dialects). These are starting points, not the scope. Additional languages, dialects, sociolects, and regional varieties are being added on an ongoing basis.

No backend. No proprietary format. Plain Python pipelines that generate queryable SQLite corpora, plus a static browser viewer for manual inspection.

## Who This Is For

- **Linguists and dialectologists** studying dialect variation, morphosyntax, aspect, polarity, agreement, pronoun systems, and regional phonology
- **Language researchers and fieldworkers** documenting under-documented dialects, colloquial speech, urban vernaculars, and spoken varieties
- **Computational linguists and NLP researchers** working on low-resource NLP, dialectal NLP, morphological generation, dialect identification, machine translation for dialects, code-switching, and robustness to non-standard language
- **Developers** building dictionaries, language learning tools, translation tools, offline lexicons, and dialect-aware applications
- **Students and independent researchers** needing open, reproducible, file-based linguistic data without API dependencies

If you search for: dialect corpus, dialectal Arabic dataset, Malay dialect dictionary, Hindi dialect conjugation, Mandarin verb dataset, low-resource language corpus, morphological paradigm dataset, cross-dialectal parallel data, open linguistics data — this repository is intended to be relevant.

## Research Problem

Standard-language resources dominate linguistics and NLP. Spoken dialects diverge systematically in:

- verb conjugation and inflectional paradigms
- tense, aspect, mood (TAM) marking
- negation and polarity strategies
- pronoun inventories and person / number / gender agreement
- nominalization, participles, masdar / verbal nouns, agent nouns, place and instrument nouns
- phonological shifts, affix alternation, colloquial reduction, and morphophonemics
- lexicon choice in everyday speech vs. formal standard

These differences break models trained only on Modern Standard Arabic, Standard Malay, Standard Hindi, or Standard Mandarin, and they are poorly covered in textbooks. OpenWorldDialects documents variation at the paradigm level, not as isolated word lists.

## What This Repository Contains

1. **Language pipelines (`py.py`)**: reproducible Python scripts for data ingestion, cleaning, phonological transformation, paradigm generation, and SQLite export. Each regional directory is self-contained.
2. **Generated SQLite dialect corpora (`*.sqlite`)**: relational tables for roots / lemmas, conjugations, and nominals, designed for direct querying in linguistic analysis and NLP pipelines.
3. **Static corpus browser (`index.html`)**: a dependency-light viewer using sql.js and IndexedDB caching for searching lemmas, filtering by dialect, aspect, polarity, person, number, gender, and inspecting generated forms. Intended for manual verification, not as a production app.
4. **Reference materials where applicable**: source notes, helper scripts, and documentation for transliteration, romanization, and orthographic normalization (e.g., Arabizi, Pinyin with tones, Devanagari romanization).

All generated forms are explicitly marked by their generative process in the pipeline code. This is a research corpus under construction, not a prescriptive grammar.

## Current Coverage (Initial, Expanding)

Coverage is versioned by directory and will grow. Do not treat the current set as complete.

- **Sinitic**: Standard Mandarin verb paradigms with Pinyin (tone-preserving), aspect particles, negation, and nominalized forms derived from open HSK vocabulary.
- **MENA / Arabic dialect continuum**: triliteral root-based paradigms across Modern Standard Arabic and regional spoken varieties including Egyptian, Levantine, Palestinian, Iraqi, Gulf, Najdi, Hijazi, Yemeni, Sudanese, Moroccan Darija, and Tunisian, with Arabic script and Arabizi romanization in parallel.
- **Austronesia / Malayic**: Standard Malay and regional / colloquial varieties including Klang Valley colloquial, Kelantanese, Terengganuan, Kedahan, Perakian, Negeri Sembilan, Sarawakian, and Sabahan, with prefix morphology (meN- / peN-), nasalization, and state-level sound shifts.
- **India / Hindi continuum**: Standard Hindi and regional / contact varieties including Bambaiya, Bhojpuri, Haryanvi, and Awadhi, with full Hindi auxiliary agreement and Romanized output.
- **Romance / Spanish**: Spanish verb paradigms generated systematically for thousands of regular and orthographically-shifting verbs, covering Standard Peninsular (vosotros), Latin American (ustedes), Rioplatense (voseo/vos), and Chilean (informal voseo).

Planned direction includes broader coverage of Arabic vernaculars, Malay archipelago varieties, South Asian regional speech, Sinitic colloquial variation, and additional unrelated families as contributors add pipelines. The schema is deliberately generic to accommodate new languages without redesign.

## Methodology

Each pipeline follows the same reproducible stages:

1. **Source lexicon acquisition** from open datasets (Wiktionary-derived Kaikki dumps, HSK lists, open bilingual dictionaries, Quranic root lists, open verb lists). Sources are cited per directory in the script header and below.
2. **Lemma filtering and normalization**: part-of-speech filtering to verbs / roots, script cleaning, diacritic stripping where appropriate, romanization normalization, deduplication.
3. **Phonology / morphophonology engine**: deterministic rules for affix allomorphy, stem alternation, tonal preservation, transliteration, and dialect-specific sound change.
4. **Paradigm generation**: exhaustive combination over dialect × aspect (past, present, future, progressive, imperative) × polarity (affirmative, negative) × person / number / gender, plus nominal paradigms (participles, infinitives, verbal nouns, agent / place / instrument nouns where applicable to the language).
5. **SQLite export**: normalized relational tables with foreign keys from conjugations / nominals to roots.

This is **rule-based paradigm generation from documented templates**, not crowd-sourced attestations and not LLM hallucination. That gives systematic coverage for computational use, but also means colloquial nuance, lexical exceptions, and sociolinguistic conditioning require ongoing native-speaker validation. Limitations are documented below.

## Data Model

Schema varies slightly by language family but follows a consistent pattern:

- `roots` / `verbs`: `id, base form, romanization / transliteration, English gloss`
  - e.g., `mother_arabic, sub_arabizi, sub_english` for Arabic; `base_root, meaning_english` for Malay / Hindi / Spanish; `base_pinyin, sub_english` for Mandarin
- `conjugations`: `id, root_id, dialect, aspect, polarity, person_id, person, number, gender, form`
  - form columns are language-appropriate: `arabic, arabizi` / `pinyin` / `phrase`
- `nominals`: `id, root_id / verb_id, category, polarity, form`
  - categories include: active participle, passive participle, noun of place, noun of tool, masdar / verbal noun, infinitive, doer forms, gerundive, mnemonic where defined

Example queries for researchers:

```sql
-- All negative past forms for a given Arabic root across dialects
SELECT dialect, aspect, polarity, person_id, arabic, arabizi
FROM conjugations
WHERE root_id = 42 AND aspect = 'past' AND polarity = 'negative';

-- Cross-dialectal parallel forms for a Malay lemma
SELECT dialect, aspect, polarity, phrase
FROM conjugations
WHERE root_id = 100 AND aspect = 'future';

-- Hindi progressive paradigms by person/number/gender
SELECT dialect, person, number, gender, phrase
FROM conjugations
WHERE root_id = 10 AND aspect = 'progressive' AND polarity = 'affirmative';
Files can be opened directly with sqlite3, DB Browser for SQLite, Python sqlite3 / pandas, or R / Julia SQLite drivers. No custom loader required.
Corpus Browser
index.html (referred to in code as Polyglot Lexicon) is a static inspection tool, not the research output itself.
Loads *.sqlite files via fetch from raw.githubusercontent.com or local path
Uses sql.js (WASM SQLite) entirely client-side
Caches downloaded packs in IndexedDB (PolyglotCache) for offline reuse
Search by lemma or English gloss, browse conjugations, filter by grammatical dimensions
Use it to spot-check paradigms during development. For systematic analysis, query the SQLite files directly.
To run locally:
# option 1: open directly
# open index.html in a browser

# option 2: serve (avoids file:// CORS issues with WASM on some browsers)
python -m http.server 8000
# then visit http://localhost:8000/
Use in NLP and Computational Linguistics Research
The corpora are designed to be immediately usable for:
low-resource NLP baselines and data augmentation
dialectal morphological generation and analysis
dialect identification and variety classification
machine translation evaluation on non-standard input (dialect → English / standard → dialect)
paraphrase and normalization across dialects
pronoun resolution and agreement modeling in morphologically rich varieties
romanized / code-mixed text handling (Arabizi, Romanized Hindi, colloquial Malay)
offline educational and dictionary applications
Typical Python usage:
import sqlite3
conn = sqlite3.connect("MENA/arabic.sqlite")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cur.fetchall())
No tokenization, training code, or model weights are included. This repository provides source data; modeling is left to downstream research.
Repository Structure
code
Text
index.html
Sinitic/
  py.py
  mandarin.sqlite
MENA/
  py.py
  arabic.sqlite
  tashkeel.js
Austronesia/
  py.py
  Malay.sqlite
India/
  py.py
  hindi.sqlite
Romance/
  py.py
  spanish.sqlite
Each py.py is the authoritative pipeline for its directory. SQLite files are generated artifacts checked in for direct use. Large source dumps and PDFs are intentionally gitignored.
Reproducibility: Rebuilding a Corpus
Requirements: Python 3, standard library only (sqlite3, json, urllib, re, xml depending on pipeline). No pip install required for core builds.
python Sinitic/py.py
python MENA/py.py
python Austronesia/py.py
python India/py.py
python Romance/py.py
Hindi requires a local kaikki-hindi.jsonl Wiktionary dump in India/ (gitignored due to size). Other pipelines fetch their open sources at build time; URLs are hardcoded in each script for traceability.
If a build fails due to upstream URL changes, file an issue with the failing URL and pipeline name. Pinning hashes / vendoring sources is on the roadmap.
Sources and Provenance
Mandarin: complete-hsk-vocabulary (open HSK word list, MIT-licensed source)
Arabic: quran-bil-quran roots dataset (Hugging Face) + fallback lexical notes in-script;sql.js runtime via CDN
Malay: FB MUSE English-Malay dictionary intersected with dariusk/corpora English verb list for POS control
Hindi: Kaikki.org Hindi Wiktionary JSONL, filtered to canonical verb lemmas ending in -ना
Spanish: FB MUSE English-Spanish intersected with dariusk/corpora English verbs for POS control, plus rule-based morphology engine
Frontend runtime: sql.js 1.8.0 (WASM SQLite)
Upstream licenses remain with their owners. Generated SQLite files inherit the licensing constraints of their source lexicons plus the pipeline code. See License below. If you are a data owner and need attribution corrected, open an issue.
Research Status and Limitations
This is active research software and data. Treat it accordingly:
Paradigms are systematic and rule-generated; they prioritize coverage over idiolectal precision.
Colloquial, slang, and rapidly changing urban forms (e.g., Bambaiya, Klang Valley colloquial, Darija) are approximations awaiting native-speaker review.
English glosses are short working glosses for search and alignment, not dictionary definitions.
Transliteration choices (Arabizi numerals, Pinyin tone marks, Hindi romanization without macrons) are documented in code and are themselves research decisions open to revision.
No claim of completeness for any dialect. Absence of a form does not mean ungrammaticality; presence does not guarantee attestation in all sub-varieties.
Validation help from native speakers, dialectologists, and field linguists is explicitly welcomed.
Contributing a New Language or Dialect
Contributions of new pipelines are the primary way this project grows. Preferred pattern:
Create a new top-level directory named by region / family (e.g., Tai/, Turkic/, Bantu/).
Add a self-contained py.py that fetches open data, documents its sources, implements phonology / paradigm logic in readable functions, and writes a SQLite file with roots, conjugations, nominals tables.
Keep dependencies to Python standard library where possible.
Add the SQLite output path to index.html language list only after manual spot-checks.
Open a pull request describing sources, license compatibility, dialect scope, and known limitations.
Linguistic accuracy notes, counterexamples, and corrections to existing templates are equally valuable as code.
License
Pipeline code and viewer code in this repository are intended as open research software. Unless a file header states otherwise, treat code contributions as MIT-licensed. Upstream lexical sources retain their original licenses. Generated SQLite corpora are derivative research artifacts subject to both pipeline licensing and source-data licensing. Commercial or large-scale redistribution users should verify source compatibility for their use case.