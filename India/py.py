import csv
import json
import os
import re
import sqlite3
import unicodedata

# =====================================================================
# 1. PHONOLOGY & TRANSLITERATION ENGINE
# =====================================================================

DEV_CONSONANTS = {
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
    'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    'ड़': 'd', 'ढ़': 'dh', 'ज़': 'z', 'फ़': 'f', 'ख़': 'kh', 'ग़': 'gh', 'क़': 'q'
}

DEV_INDEPENDENT_VOWELS = {
    # NOTE: आ maps to 'a' (not 'aa') to stay consistent with the matra ा->'a'
    # and IAST ā normalization below, so Strategy A/B never yield duplicate
    # roots like 'a' vs 'aa' for आना.
    'अ': 'a', 'आ': 'a', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo',
    'ऋ': 'ri', 'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au'
}

DEV_MATRAS = {
    'ा': 'a', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
    'ृ': 'ri', 'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au'
}

def transliterate_devanagari_stem(dev_stem: str) -> str:
    """Accurately converts a Devanagari verb stem (e.g. 'कर', 'देख', 'खा') to Roman script."""
    text = (dev_stem.replace('क\u093c', 'क़')
                    .replace('ख\u093c', 'ख़')
                    .replace('ग\u093c', 'ग़')
                    .replace('ज\u093c', 'ज़')
                    .replace('ड\u093c', 'ड़')
                    .replace('ढ\u093c', 'ढ़')
                    .replace('फ\u093c', 'फ़'))

    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]

        # Nasalizers
        if c in ['\u0901', '\u0902']:
            out.append('n')
            i += 1
            continue

        # Independent vowels
        if c in DEV_INDEPENDENT_VOWELS:
            out.append(DEV_INDEPENDENT_VOWELS[c])
            i += 1
            continue

        # Consonants
        if c in DEV_CONSONANTS:
            base = DEV_CONSONANTS[c]
            if i + 1 < n and text[i+1] == '\u094d':  # Virama / Halant
                out.append(base)
                i += 2
            elif i + 1 < n and text[i+1] in DEV_MATRAS:
                out.append(base + DEV_MATRAS[text[i+1]])
                i += 2
            elif i + 1 == n or text[i+1] == " ":
                # Schwa deletion at the end of a word, not just the end of
                # the whole stem: "अभिनय कर" -> "abhinay kar" (never
                # *"abhinaya kar"), "धन्यवाद दे" -> "dhanyavad de".
                out.append(base)
                i += 1
            else:
                out.append(base + 'a')
                i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def normalize_wiktionary_romanization(roman: str) -> str:
    """Cleans Indological macrons/diacritics into standard Roman phonetic forms."""
    text = roman.replace("ā", "a").replace("ī", "ee").replace("ū", "oo")
    text = text.replace("ē", "e").replace("ō", "o")
    text = text.replace("ḍh", "dh").replace("ṛh", "rh").replace("ḍ", "d").replace("ṛ", "d")
    text = text.replace("ṭh", "th").replace("ṭ", "t")
    text = text.replace("ṇ", "n").replace("ñ", "n").replace("ṅ", "ng")
    text = text.replace("ś", "sh").replace("ṣ", "sh")
    text = text.replace("͠", "n").replace("̃", "n")

    # Strip any remaining Unicode accents
    nfkd = unicodedata.normalize('NFKD', text)
    clean = "".join(c for c in nfkd if unicodedata.category(c) != 'Mn')
    # FATAL FIX: preserve internal spaces so compound verb stems
    # (e.g. अभिनय कर, धन्यवाद दे) stay "abhinay kar", not merged garbage
    # like "abhinaykar" which would conjugate as *"abhinaykarta hai".
    clean = re.sub(r"[^a-zA-Z ]", "", clean.lower())
    return re.sub(r"\s+", " ", clean).strip()


class HindiPhonologyEngine:
    @staticmethod
    def ta_ti_te(pid: str) -> str:
        if pid in ["1fs", "2fs", "2fp", "3fs", "1fp", "3fp"]: return "ti"
        if pid in ["1ms", "2ms", "3ms"]: return "ta"
        return "te"

    @staticmethod
    def raha_rahi_rahe(pid: str) -> str:
        if pid in ["1fs", "2fs", "2fp", "3fs", "1fp", "3fp"]: return "rahi"
        if pid in ["1ms", "2ms", "3ms"]: return "raha"
        return "rahe"

    @staticmethod
    def hu_hai_ho_hain(pid: str) -> str:
        if pid in ["1ms", "1fs"]: return "hu"
        if pid in ["2mp", "2fp"]: return "ho"
        if pid in ["2pol", "1mp", "1fp", "3mp", "3fp"]: return "hain"
        return "hai"

    @staticmethod
    def tha_thi_the(pid: str) -> str:
        if pid in ["1fs", "2fs", "2fp", "3fs", "1fp", "3fp"]: return "thi"
        if pid in ["1ms", "2ms", "3ms"]: return "tha"
        return "the"

    @staticmethod
    def future_suffix(pid: str) -> str:
        mapping = {
            "1ms": "unga", "1fs": "ungi",
            "2ms": "ega", "2fs": "egi",
            "2mp": "oge", "2fp": "ogi",
            "2pol": "enge",
            "3ms": "ega", "3fs": "egi",
            "1mp": "enge", "1fp": "engi",
            "3mp": "enge", "3fp": "engi"
        }
        return mapping[pid]

    # होना is suppletive in the future (होगा, not *होएगा).
    HO_FUTURE = {
        "unga": "hoonga", "ega": "hoga", "egi": "hogi",
        "oge": "hoge", "ogi": "hogi", "enge": "honge", "engi": "hongi",
    }

    @staticmethod
    def apply_suffix(root: str, suffix: str) -> str:
        if not suffix: return root
        # Compound stems (kept with spaces, e.g. "abhinay kar"): inflect only
        # the final element so we get "abhinay karega", never *"abhinaykarega".
        if " " in root:
            head, _, tail = root.rpartition(" ")
            return head + " " + HindiPhonologyEngine.apply_suffix(tail, suffix)
        if root == "ho" and suffix in HindiPhonologyEngine.HO_FUTURE:
            return HindiPhonologyEngine.HO_FUTURE[suffix]
        if root.endswith("ee") and suffix[:1] in "aeiou":
            # पीएगा = "piega" (not *"peeega"); पीओ = "piyo".
            if suffix.startswith("e"):
                return root[:-2] + "i" + suffix
            return root[:-2] + "iy" + suffix
        # NOTE: no oo->uw rule: छूएगा = "chooega" (concat), not *"chuwega".
        if root.endswith("e") and suffix[:1] == "a":
            # दे + ab/at -> deb/det (Awadhi/Bhojpuri), not *deab/*deat.
            return root + suffix[1:]
        if root.endswith("e") and suffix[:1] in "eiou":
            # दे + ega/iye/o -> dega/diye/do (not *deega/*deiye/*deo).
            return root[:-1] + suffix
        return root + suffix


# =====================================================================
# 2. PIPELINE & DATA INGESTION
# =====================================================================

class HindiRomanizedRootPipeline:
    def __init__(self, dataset_file_path: str = None):
        self.phonology = HindiPhonologyEngine()
        self.dataset_file_path = dataset_file_path or self._auto_locate_dataset()

        self.dialects = [
            {"code": "standard", "name": "Standard Romanized (Khariboli)"},
            {"code": "bambaiya", "name": "Bambaiya (Mumbai Slang)"},
            {"code": "bhojpuri", "name": "Bhojpuri (Romanized)"},
            {"code": "haryanvi", "name": "Haryanvi (Romanized)"},
            {"code": "awadhi", "name": "Awadhi (Romanized)"}
        ]

        self.persons = [
            {"id": "1ms", "p": "1", "n": "sg", "g": "m"},
            {"id": "1fs", "p": "1", "n": "sg", "g": "f"},
            {"id": "2ms", "p": "2", "n": "sg", "g": "m"},
            {"id": "2fs", "p": "2", "n": "sg", "g": "f"},
            {"id": "2mp", "p": "2", "n": "pl", "g": "m"},
            {"id": "2fp", "p": "2", "n": "pl", "g": "f"},
            {"id": "2pol", "p": "2", "n": "pl", "g": "c"},
            {"id": "3ms", "p": "3", "n": "sg", "g": "m"},
            {"id": "3fs", "p": "3", "n": "sg", "g": "f"},
            {"id": "1mp", "p": "1", "n": "pl", "g": "m"},
            {"id": "1fp", "p": "1", "n": "pl", "g": "f"},
            {"id": "3mp", "p": "3", "n": "pl", "g": "m"},
            {"id": "3fp", "p": "3", "n": "pl", "g": "f"},
        ]

        self.imperative_persons = [
            {"id": "2ms", "p": "2", "n": "sg", "g": "m"},
            {"id": "2fs", "p": "2", "n": "sg", "g": "f"},
            {"id": "2mp", "p": "2", "n": "pl", "g": "m"},
            {"id": "2fp", "p": "2", "n": "pl", "g": "f"},
            {"id": "2pol", "p": "2", "n": "pl", "g": "c"},
        ]

        self.pronouns_map = {
            "standard": {"1ms": "main", "1fs": "main", "2ms": "tu", "2fs": "tu", "2mp": "tum", "2fp": "tum", "2pol": "aap", "3ms": "woh", "3fs": "woh", "1mp": "hum", "1fp": "hum", "3mp": "wo", "3fp": "wo"},
            "bambaiya": {"1ms": "apun", "1fs": "apun", "2ms": "tu", "2fs": "tu", "2mp": "tum", "2fp": "tum", "2pol": "aap", "3ms": "wo", "3fs": "wo", "1mp": "apun", "1fp": "apun", "3mp": "wo log", "3fp": "wo log"},
            "bhojpuri": {"1ms": "hum", "1fs": "hum", "2ms": "tu", "2fs": "tu", "2mp": "toh log", "2fp": "toh log", "2pol": "raua", "3ms": "oo", "3fs": "oo", "1mp": "hamni", "1fp": "hamni", "3mp": "oo log", "3fp": "oo log"},
            "haryanvi": {"1ms": "main", "1fs": "main", "2ms": "tu", "2fs": "tu", "2mp": "tam", "2fp": "tam", "2pol": "aap", "3ms": "wo", "3fs": "wo", "1mp": "ham", "1fp": "ham", "3mp": "we", "3fp": "we"},
            "awadhi": {"1ms": "hum", "1fs": "hum", "2ms": "tum", "2fs": "tum", "2mp": "tum sab", "2fp": "tum sab", "2pol": "aap", "3ms": "oo", "3fs": "oo", "1mp": "hum sab", "1fp": "hum sab", "3mp": "oo sab", "3fp": "oo sab"},
        }

    def _auto_locate_dataset(self) -> str:
        """Looks for Kaikki or JSONL files in the current folder automatically."""
        for fname in os.listdir("."):
            if fname.endswith(".jsonl") or ("kaikki" in fname.lower() and fname.endswith(".json")):
                return fname
        return None

    def parse_kaikki_jsonl(self, file_path: str) -> list:
        print(f"Reading Kaikki dataset from: {file_path}")
        results = []
        seen_roots = set()

        with open(file_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except Exception:
                    continue

                # 1. Must be a Hindi verb
                if entry.get("pos") != "verb":
                    continue
                lang = entry.get("lang_code") or entry.get("lang")
                if lang not in ["hi", "Hindi"]:
                    continue

                # 2. Filter out inflected forms (only keep canonical base lemmas)
                senses = entry.get("senses", [])
                is_inflected = False
                meaning = ""
                for s in senses:
                    tags = s.get("tags", [])
                    if "form-of" in tags or "inflection-template" in tags or s.get("form_of"):
                        is_inflected = True
                        break
                    if not meaning and s.get("glosses"):
                        meaning = s.get("glosses")[0]

                if is_inflected:
                    continue

                raw_word = entry.get("word", "").strip()

                # 3. Canonical Hindi lemma verbs end in '-ना'
                if not raw_word.endswith("ना"):
                    continue

                # 4. Resolve the Romanized base root
                base_root = ""
                # Strategy A: Check Wiktionary romanization
                for form_info in entry.get("forms", []):
                    if "romanization" in form_info.get("tags", []):
                        r_form = form_info.get("form", "")
                        clean_r = normalize_wiktionary_romanization(r_form)
                        if clean_r.endswith("na") and len(clean_r) > 2:
                            base_root = clean_r[:-2]
                        break

                # Strategy B: Fallback to direct Devanagari stem transliteration
                if not base_root:
                    dev_stem = raw_word[:-2]  # strip 'ना'
                    base_root = transliterate_devanagari_stem(dev_stem)

                # FATAL FIX: keep internal spaces for compound stems
                # ("abhinay kar", not *"abhinaykar").
                base_root = re.sub(r"[^a-zA-Z ]", "", base_root.lower())
                base_root = re.sub(r"\s+", " ", base_root).strip()

                # Basic validation
                valid_short_roots = {"a", "ja", "kha", "pi", "pee", "so", "ro", "dho", "ho", "de", "le"}
                if not base_root or (len(base_root) < 2 and base_root not in valid_short_roots):
                    continue

                if base_root in seen_roots:
                    continue
                seen_roots.add(base_root)

                results.append({
                    "root": base_root,
                    "meaning_en": meaning or "Hindi verb action"
                })

        print(f"Extracted {len(results)} valid base verb roots from Kaikki dump.")
        return results

    def generate_full_paradigm(self, root: str):
        engine = self.phonology
        dialect_conjugations = {}

        for dialect_info in self.dialects:
            code = dialect_info["code"]
            pronouns = self.pronouns_map[code]
            aspects_data = {}

            past_aff, past_neg = {}, {}
            pres_aff, pres_neg = {}, {}
            fut_aff, fut_neg = {}, {}
            prog_aff, prog_neg = {}, {}
            imp_aff, imp_neg = {}, {}

            for p_data in self.persons:
                pid = p_data["id"]
                pro = pronouns[pid]

                t3 = engine.ta_ti_te(pid)
                r3 = engine.raha_rahi_rahe(pid)
                h3 = engine.hu_hai_ho_hain(pid)
                th3 = engine.tha_thi_the(pid)
                fut_s = engine.future_suffix(pid)

                # Standard
                if code == "standard":
                    pres_aff[pid] = f"{pro} {root}{t3} {h3}"
                    pres_neg[pid] = f"{pro} nahi {root}{t3}"
                    past_aff[pid] = f"{pro} {root}{t3} {th3}"
                    past_neg[pid] = f"{pro} nahi {root}{t3} {th3}"
                    f_verb = engine.apply_suffix(root, fut_s)
                    fut_aff[pid] = f"{pro} {f_verb}"
                    fut_neg[pid] = f"{pro} nahi {f_verb}"
                    prog_aff[pid] = f"{pro} {root} {r3} {h3}"
                    prog_neg[pid] = f"{pro} {root} nahi {r3} {h3}"

                # Bambaiya
                elif code == "bambaiya":
                    rela = "reli" if "f" in pid else "rela"
                    pres_aff[pid] = f"{pro} {root}{rela} hai"
                    pres_neg[pid] = f"{pro} nahi {root}{rela} hai"
                    past_aff[pid] = f"{pro} {root}{rela} {th3}"
                    past_neg[pid] = f"{pro} nahi {root}{rela} {th3}"
                    # Bambaiya future follows the standard pattern
                    # ("karega", never *"karyega").
                    f_suf = "egi" if "f" in pid else "ega"
                    f_verb = engine.apply_suffix(root, f_suf)
                    fut_aff[pid] = f"{pro} {f_verb}"
                    fut_neg[pid] = f"{pro} nahi {f_verb}"
                    prog_aff[pid] = f"{pro} {root}{rela} hai"
                    prog_neg[pid] = f"{pro} nahi {root}{rela} hai"

                # Bhojpuri
                elif code == "bhojpuri":
                    b_pres = "at bani" if pid.startswith("1") else "at bada" if pid.startswith("2") else "at ba"
                    b_past = "at rahni" if pid.startswith("1") else "at rahla" if pid.startswith("2") else "at rahal"
                    b_fut = "ab" if pid.startswith("1") else "ba" if pid.startswith("2") else "i"
                    pres_aff[pid] = f"{pro} {root}{b_pres}"
                    pres_neg[pid] = f"{pro} na {root}{b_pres}"
                    past_aff[pid] = f"{pro} {root}{b_past}"
                    past_neg[pid] = f"{pro} na {root}{b_past}"
                    fut_aff[pid] = f"{pro} {root}{b_fut}"
                    fut_neg[pid] = f"{pro} na {root}{b_fut}"
                    prog_aff[pid] = f"{pro} {root}{b_pres}"
                    prog_neg[pid] = f"{pro} na {root}{b_pres}"

                # Haryanvi auxiliaries: 1st person सूं ("sun"),
                # plural सो ("so"), 3rd सै ("se").
                elif code == "haryanvi":
                    h_aux = "sun" if pid.startswith("1") else "so" if "p" in pid else "se"
                    pres_aff[pid] = f"{pro} {root}{t3} {h_aux}"
                    pres_neg[pid] = f"{pro} na {root}{t3} {h_aux}"
                    past_aff[pid] = f"{pro} {root}{t3} {th3}"
                    past_neg[pid] = f"{pro} na {root}{t3} {th3}"
                    f_verb = engine.apply_suffix(root, fut_s)
                    fut_aff[pid] = f"{pro} {f_verb}"
                    fut_neg[pid] = f"{pro} na {f_verb}"
                    prog_aff[pid] = f"{pro} {root} {r3} {h_aux}"
                    prog_neg[pid] = f"{pro} na {root} {r3} {h_aux}"

                # Awadhi (present/past marker is -at-: "karat hai",
                # never *"karit hai" — progressive below already used "at").
                elif code == "awadhi":
                    pres_aff[pid] = f"{pro} {root}at hai"
                    pres_neg[pid] = f"{pro} na {root}at hai"
                    past_aff[pid] = f"{pro} {root}at raha"
                    past_neg[pid] = f"{pro} na {root}at raha"
                    fut_aff[pid] = f"{pro} {root}ab"
                    fut_neg[pid] = f"{pro} na {root}ab"
                    prog_aff[pid] = f"{pro} {root}at hai"
                    prog_neg[pid] = f"{pro} na {root}at hai"

            # Imperatives
            for p_data in self.imperative_persons:
                pid = p_data["id"]
                pro = pronouns[pid]
                if code in ["standard", "haryanvi"]:
                    suf = "o" if "p" in pid and pid != "2pol" else "iye" if pid == "2pol" else ""
                    imp_aff[pid] = f"{pro} {engine.apply_suffix(root, suf)}".strip()
                    imp_neg[pid] = f"{pro} mat {engine.apply_suffix(root, suf)}".strip()
                elif code == "bambaiya":
                    imp_aff[pid] = f"{pro} {root}"
                    imp_neg[pid] = f"{pro} mat {root}"
                elif code == "bhojpuri":
                    suf = "a" if "p" in pid and pid != "2pol" else "in" if pid == "2pol" else ""
                    imp_aff[pid] = f"{pro} {root}{suf}".strip()
                    # Eastern prohibitive is जिन ("jin"); "jani" means
                    # "having known" and is never a prohibitive.
                    imp_neg[pid] = f"{pro} jin {root}{suf}".strip()
                elif code == "awadhi":
                    suf = "o" if "p" in pid else ""
                    imp_aff[pid] = f"{pro} {root}{suf}".strip()
                    imp_neg[pid] = f"{pro} jin {root}{suf}".strip()

            aspects_data["past"] = {"affirmative": past_aff, "negative": past_neg}
            aspects_data["present"] = {"affirmative": pres_aff, "negative": pres_neg}
            aspects_data["future"] = {"affirmative": fut_aff, "negative": fut_neg}
            aspects_data["progressive"] = {"affirmative": prog_aff, "negative": prog_neg}
            aspects_data["imperative"] = {"affirmative": imp_aff, "negative": imp_neg}
            dialect_conjugations[code] = aspects_data

        return dialect_conjugations

    def generate_nominals(self, root: str):
        return {
            "infinitive": {"phrase": f"{root}na"},
            "doer_masculine_sg": {"phrase": f"{root}ne wala"},
            "doer_feminine_sg": {"phrase": f"{root}ne wali"},
            "doer_plural": {"phrase": f"{root}ne wale"},
            "gerundive": {"phrase": f"{root}te hue"}
        }

    # NOTE: filename must match index.html loader (India/hindi.sqlite).
    def build_database(self, db_path: str = "hindi.sqlite", limit: int = None):
        if not self.dataset_file_path or not os.path.exists(self.dataset_file_path):
            print(f"Error: Dataset file '{self.dataset_file_path}' not found.")
            return

        dataset = self.parse_kaikki_jsonl(self.dataset_file_path)
        if limit:
            dataset = dataset[:limit]

        print(f"Building SQLite database from {len(dataset)} base roots...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # NOTE: no synchronous=OFF / journal_mode=MEMORY here. Those bulk-load
        # pragmas turn any killed build into a permanently corrupt database
        # ("database disk image is malformed" on the next run); the shipped
        # hindi.sqlite died exactly that way. Default journaling is slower
        # but crash-safe; a rebuild is always reproducible from the dump.
        cursor.execute("PRAGMA foreign_keys = ON;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_root TEXT UNIQUE,
                meaning_english TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nominals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_id INTEGER,
                category TEXT,
                phrase TEXT,
                FOREIGN KEY(root_id) REFERENCES roots(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conjugations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_id INTEGER,
                dialect TEXT,
                aspect TEXT,
                polarity TEXT,
                person_id TEXT,
                person TEXT,
                number TEXT,
                gender TEXT,
                phrase TEXT,
                FOREIGN KEY(root_id) REFERENCES roots(id)
            )
        """)

        cursor.execute("DELETE FROM conjugations")
        cursor.execute("DELETE FROM nominals")
        cursor.execute("DELETE FROM roots")

        processed = 0
        total = len(dataset)
        for idx, item in enumerate(dataset):
            base_root = item["root"]
            raw_english = item["meaning_en"]

            try:
                cursor.execute("INSERT INTO roots (base_root, meaning_english) VALUES (?, ?)", (base_root, raw_english))
                root_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                continue

            # Nominals
            noms = self.generate_nominals(base_root)
            nom_tuples = [(root_id, cat, d["phrase"]) for cat, d in noms.items()]
            cursor.executemany("INSERT INTO nominals (root_id, category, phrase) VALUES (?, ?, ?)", nom_tuples)

            # Full Conjugations
            dialects_dict = self.generate_full_paradigm(base_root)
            conj_tuples = []
            for d in self.dialects:
                d_code = d["code"]
                for aspect, pol_dict in dialects_dict[d_code].items():
                    for pol, p_dict in pol_dict.items():
                        for pid, phrase in p_dict.items():
                            p_info = next((x for x in self.persons if x["id"] == pid), None)
                            if not p_info:
                                p_info = next((x for x in self.imperative_persons if x["id"] == pid), {"p": "2", "n": "sg", "g": "m"})
                            conj_tuples.append((
                                root_id, d_code, aspect, pol, pid,
                                p_info["p"], p_info["n"], p_info["g"], phrase
                            ))

            cursor.executemany("""
                INSERT INTO conjugations (root_id, dialect, aspect, polarity, person_id, person, number, gender, phrase)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, conj_tuples)

            processed += 1
            if processed % 100 == 0 or processed == total:
                # FATAL FIX: meanings carry macrons/Devanagari that crash
                # Windows cp1252 consoles mid-build (leaving a half-written,
                # corrupt database behind). Print ASCII-safe progress only.
                safe_meaning = raw_english[:35].encode("ascii", "replace").decode("ascii")
                safe_root = base_root.encode("ascii", "replace").decode("ascii")
                print(f"[{processed}/{total}] Processed: '{safe_root}' ({safe_meaning}...)")

        conn.commit()
        conn.close()
        print(f"\nDone! Database '{db_path}' contains {processed} roots and over {processed * 570:,} conjugations.")


# =====================================================================
# 3. RUNNER
# =====================================================================

if __name__ == "__main__":
    # Point directly to your downloaded Kaikki dump or let it auto-detect:
    pipeline = HindiRomanizedRootPipeline(dataset_file_path="kaikki-hindi.jsonl")
    
    # Process all parsed roots (or pass limit=500 to test a subset)
    pipeline.build_database(limit=None)