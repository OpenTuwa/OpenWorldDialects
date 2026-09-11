import json
import re
import ssl
import sqlite3
import urllib.error
import urllib.request


class MITLicensedMandarinPipeline:
    def __init__(self):
        # Strictly Standard Mandarin (no dialects)
        self.dialects = [
            {"code": "standard", "name": "Standard Mandarin", "region": "Pan-Chinese"}
        ]

        # Pronoun mapping for Pinyin (Tones included)
        self.persons = [
            {"id": "1s", "p": "1", "n": "sg", "g": "c", "name": "I", "pinyin": "wǒ"},
            {"id": "2s", "p": "2", "n": "sg", "g": "c", "name": "You", "pinyin": "nǐ"},
            {"id": "3ms", "p": "3", "n": "sg", "g": "m", "name": "He", "pinyin": "tā"},
            {"id": "3fs", "p": "3", "n": "sg", "g": "f", "name": "She", "pinyin": "tā"},
            {"id": "1p", "p": "1", "n": "pl", "g": "c", "name": "We", "pinyin": "wǒmen"},
            {"id": "2p", "p": "2", "n": "pl", "g": "c", "name": "You All", "pinyin": "nǐmen"},
            {"id": "3p", "p": "3", "n": "pl", "g": "c", "name": "They", "pinyin": "tāmen"},
        ]

        self.imperative_persons = [
            {"id": "2s", "p": "2", "n": "sg", "g": "c", "pinyin": "nǐ"},
            {"id": "2p", "p": "2", "n": "pl", "g": "c", "pinyin": "nǐmen"},
        ]

    def sanitize_pinyin(self, pinyin_text: str) -> str:
        """
        Cleans pinyin but strictly PRESERVES tonal diacritics (ā á ǎ à).
        Without these, a tonal language loses all context.
        """
        if not pinyin_text:
            return ""
        
        # Strip numbers and any Chinese characters/punctuation.
        # Whitelist standard english alphabet + Pinyin tone characters + spaces.
        cleaned = re.sub(r'[^a-zA-Z\sāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüĀÁǍÀĒÉĚÈĪÍǏÌŌÓǑÒŪÚǓÙǕǗǙǛÜ]', '', pinyin_text)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip().lower()

    def format_english_definition(self, raw_text: str) -> str:
        """
        STRICT VERB FILTER:
        Analyzes definitions. If it's a noun/adjective/interjection, it returns empty (triggering a skip).
        It only allows actual verbs (starting with "to "), keeping definitions clean and short.
        """
        # Remove bracketed context
        text = re.sub(r'\(.*?\)', '', raw_text).strip()
        
        # Split by semicolons or slashes to evaluate distinct definitions
        parts = re.split(r'[;/]', text)
        
        for part in parts:
            part = part.strip()
            # MUST start with "to " (e.g., "to eat", "to take a beating"). 
            # This completely filters out nouns like "cancer" or interjections like "aiya".
            if part.lower().startswith("to "):
                clean_def = re.sub(r'\s+', ' ', part)
                
                # Cut at the first comma (e.g., "to entreat, to implore" -> "to entreat")
                clean_def = clean_def.split(',')[0].strip()
                
                # Truncate to maximum 6 words to allow phrases, but prevent paragraphs
                words = clean_def.split()
                if len(words) > 6:
                    clean_def = " ".join(words[:6])
                    
                return clean_def.capitalize()
                
        # If no verb definition was found, return empty string to discard the word entirely
        return ""

    # Stative verbs that reject the perfective 了 and progressive 在.
    # 是 never takes 了 ("*shì le") and negates with 不 even in the past
    # ("bú shì", never *"méi shì"); 有/在/像 follow the per-verb rules below.
    # Matched on the EXACT monosyllabic base only, so compounds like
    # "shìyìng" (to adapt, action verb) are unaffected.
    STATIVE_RULES = {
        # copula/identity: no le/zài anywhere; past neg uses bù
        "shì":   {"past_aff": "", "past_neg": "bú ", "prog_aff": "",
                  "prog_neg": "bú ", "imp_aff": "yào ", "imp_neg": "bú yào "},
        "xiàng": {"past_aff": "", "past_neg": "bú ", "prog_aff": "",
                  "prog_neg": "bú ", "imp_aff": "yào ", "imp_neg": "bú yào "},
        # possession: "yǒu le" OK, "méi yǒu" OK; only progressive is barred
        "yǒu":   {"past_aff": " le", "past_neg": "méi ", "prog_aff": "",
                  "prog_neg": "méi ", "imp_aff": "yào ", "imp_neg": "bú yào "},
        # location: past neg "méi zài" OK; bare forms elsewhere (avoids
        # *"zài le" and *"zài zài")
        "zài":   {"past_aff": "", "past_neg": "méi ", "prog_aff": "",
                  "prog_neg": "méi ", "imp_aff": "yào ", "imp_neg": "bú yào "},
    }

    def generate_full_paradigm(self, base_word: str):
        """Generates pronouns combined with base words and Mandarin aspect particles."""
        dialect_conjugations = {}

        # Mandarin Aspect Markers
        spec = {
            "past_aff": " le",
            "past_neg": "méi ",
            "pres_aff": "",
            "pres_neg": "bù ",
            "fut_aff": "huì ",
            "fut_neg": "bú huì ",
            "prog_aff": "zài ",
            "prog_neg": "méi zài ",
        }

        st = self.STATIVE_RULES.get(base_word)
        if st:
            spec = dict(spec)
            spec["past_aff"] = st["past_aff"]
            spec["past_neg"] = st["past_neg"]
            spec["prog_aff"] = st["prog_aff"]
            spec["prog_neg"] = st["prog_neg"]

        for d in self.dialects:
            code = d["code"]
            aspects_data = {}

            past_aff, past_neg = {}, {}
            for p in self.persons:
                pid, pron = p["id"], p["pinyin"]
                past_aff[pid] = {"pinyin": f"{pron} {base_word}{spec['past_aff']}"}
                past_neg[pid] = {"pinyin": f"{pron} {spec['past_neg']}{base_word}"}
            aspects_data["past"] = {"affirmative": past_aff, "negative": past_neg}

            pres_aff, pres_neg = {}, {}
            for p in self.persons:
                pid, pron = p["id"], p["pinyin"]
                pres_aff[pid] = {"pinyin": f"{pron} {base_word}"}
                pres_neg[pid] = {"pinyin": f"{pron} {spec['pres_neg']}{base_word}"}
            aspects_data["present"] = {"affirmative": pres_aff, "negative": pres_neg}

            fut_aff, fut_neg = {}, {}
            for p in self.persons:
                pid, pron = p["id"], p["pinyin"]
                fut_aff[pid] = {"pinyin": f"{pron} {spec['fut_aff']}{base_word}"}
                fut_neg[pid] = {"pinyin": f"{pron} {spec['fut_neg']}{base_word}"}
            aspects_data["future"] = {"affirmative": fut_aff, "negative": fut_neg}

            prog_aff, prog_neg = {}, {}
            for p in self.persons:
                pid, pron = p["id"], p["pinyin"]
                prog_aff[pid] = {"pinyin": f"{pron} {spec['prog_aff']}{base_word}"}
                prog_neg[pid] = {"pinyin": f"{pron} {spec['prog_neg']}{base_word}"}
            aspects_data["progressive"] = {"affirmative": prog_aff, "negative": prog_neg}

            imp_aff, imp_neg = {}, {}
            for ip in self.imperative_persons:
                pid, pron = ip["id"], ip["pinyin"]
                if st:
                    # Statives take no 请 ("*qǐng shì"); 要-command instead.
                    imp_aff[pid] = {"pinyin": f"{pron} {st['imp_aff']}{base_word}"}
                    imp_neg[pid] = {"pinyin": f"{pron} {st['imp_neg']}{base_word}"}
                else:
                    imp_aff[pid] = {"pinyin": f"{pron} qǐng {base_word}"}
                    imp_neg[pid] = {"pinyin": f"{pron} qǐng bú yào {base_word}"}
            aspects_data["imperative"] = {"affirmative": imp_aff, "negative": imp_neg}

            dialect_conjugations[code] = aspects_data

        return dialect_conjugations

    def generate_nominals(self, base_word: str):
        return {
            "active_participle": {
                "affirmative": {"pinyin": f"{base_word} de rén"},         
                "negative":    {"pinyin": f"bù {base_word} de rén"}       
            },
            "passive_participle": {
                "affirmative": {"pinyin": f"bèi {base_word} de"},         
                "negative":    {"pinyin": f"méi bèi {base_word} de"}      
            },
            "noun_of_place": {
                "affirmative": {"pinyin": f"{base_word} de dìfāng"},      
                "negative":    {"pinyin": f"bù {base_word} de dìfāng"}    
            },
            "noun_of_tool": {
                "affirmative": {"pinyin": f"{base_word} de gōngjù"},      
                "negative":    {"pinyin": f"bù néng {base_word} de gōngjù"} 
            },
            "masdar": {
                "affirmative": {"pinyin": f"{base_word} de shì"},         
                "negative":    {"pinyin": f"bù {base_word} de shì"}       
            }
        }

    def fetch_hsk_dataset(self) -> list:
        """Dynamically fetches the open-source MIT-licensed HSK Vocabulary list."""
        url = "https://raw.githubusercontent.com/drkameleon/complete-hsk-vocabulary/main/complete.json"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        print("Fetching open-source HSK Mandarin dataset...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx) as response:
                data = json.loads(response.read().decode("utf-8"))

            words_data = []
            
            for item in data:
                try:
                    forms = item.get("forms", [])
                    if not forms:
                        continue
                        
                    raw_pinyin = forms[0].get("transcriptions", {}).get("pinyin", "")
                    meanings_list = forms[0].get("meanings", [])
                    
                    if not raw_pinyin or not meanings_list:
                        continue
                        
                    # Join all possible meanings into a single string so our verb filter can evaluate them
                    raw_english_joined = " ; ".join(meanings_list)
                    
                    words_data.append({
                        "pinyin_raw": raw_pinyin,
                        "meaning_en": raw_english_joined
                    })
                except Exception:
                    pass
                    
            print(f"Success! Evaluating {len(words_data)} HSK words for verbs...")
            return words_data
        except Exception as e:
            print(f"Failed to fetch dataset: {e}")
            return []

    def build_database(self):
        dataset = self.fetch_hsk_dataset()
        if not dataset:
            print("No data loaded. Exiting build process.")
            return
        
        # NOTE: filename must match index.html loader (Sinitic/mandarin.sqlite).
        db_path = "mandarin.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verbs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_pinyin TEXT UNIQUE,
                sub_english TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nominals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verb_id INTEGER,
                category TEXT,
                polarity TEXT,
                pinyin TEXT,
                FOREIGN KEY(verb_id) REFERENCES verbs(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conjugations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verb_id INTEGER,
                dialect TEXT,
                aspect TEXT,
                polarity TEXT,
                person_id TEXT,
                person TEXT,
                number TEXT,
                gender TEXT,
                pinyin TEXT,
                FOREIGN KEY(verb_id) REFERENCES verbs(id)
            )
        """)
        
        cursor.execute("DELETE FROM conjugations")
        cursor.execute("DELETE FROM nominals")
        cursor.execute("DELETE FROM verbs")

        inserted_count = 0

        for item in dataset:
            raw_pinyin = item.get("pinyin_raw", "")
            base_pinyin = self.sanitize_pinyin(raw_pinyin)

            if not base_pinyin or len(base_pinyin) <= 1:
                continue

            raw_english = item.get("meaning_en", "")
            
            # This is the magic filter. If it's not an action verb, it returns empty.
            formatted_english = self.format_english_definition(raw_english)

            # SKIP if the word isn't a verb (This stops Nouns/Interjections from entering the DB)
            if not formatted_english:
                continue

            try:
                cursor.execute("""
                    INSERT INTO verbs (base_pinyin, sub_english)
                    VALUES (?, ?)
                """, (base_pinyin, formatted_english))
                verb_id = cursor.lastrowid
                inserted_count += 1
            except sqlite3.IntegrityError:
                continue

            # Generate and insert nominalizations
            nominals = self.generate_nominals(base_pinyin)
            nom_tuples = []
            for n_type, polarities in nominals.items():
                for pol, scripts in polarities.items():
                    nom_tuples.append((verb_id, n_type, pol, scripts["pinyin"]))
            
            cursor.executemany("""
                INSERT INTO nominals (verb_id, category, polarity, pinyin)
                VALUES (?, ?, ?, ?)
            """, nom_tuples)

            # Generate and insert grammar conjugations
            dialectal_conjugations = self.generate_full_paradigm(base_pinyin)
            conj_tuples = []
            for d in self.dialects:
                d_code = d["code"]
                d_conjugations = dialectal_conjugations.get(d_code, {})
                for aspect, pol_dict in d_conjugations.items():
                    for pol, persons_dict in pol_dict.items():
                        for pid, scripts in persons_dict.items():
                            p_info = next((x for x in self.persons if x["id"] == pid), None)
                            if not p_info:
                                p_info = next((x for x in self.imperative_persons if x["id"] == pid), {"p": "2", "n": "sg", "g": "c"})
                            
                            conj_tuples.append((
                                verb_id, d_code, aspect, pol, pid,
                                p_info["p"], p_info["n"], p_info["g"],
                                scripts["pinyin"]
                            ))

            cursor.executemany("""
                INSERT INTO conjugations (
                    verb_id, dialect, aspect, polarity, person_id, person, number, gender, pinyin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, conj_tuples)

        conn.commit()
        conn.close()
        print(f"Database generation complete! Filtered down to {inserted_count} pure verbs. Saved to {db_path}")


if __name__ == "__main__":
    pipeline = MITLicensedMandarinPipeline()
    pipeline.build_database()