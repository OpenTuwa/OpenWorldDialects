import gzip
import json
import re
import ssl
import sqlite3
import unicodedata
import urllib.error
import urllib.request


_TONE_MARKS = {
    'a': ['ā', 'á', 'ǎ', 'à'], 'e': ['ē', 'é', 'ě', 'è'],
    'i': ['ī', 'í', 'ǐ', 'ì'], 'o': ['ō', 'ó', 'ǒ', 'ò'],
    'u': ['ū', 'ú', 'ǔ', 'ù'], 'ü': ['ǖ', 'ǘ', 'ǚ', 'ǜ'],
}


def cedict_syllable_to_diac(syl: str):
    """Converts one numbered pinyin syllable (ni3, lü4, zhong1, wan2r) to diacritics."""
    # CC-CEDICT writes erhua with the r AFTER the tone digit ("wan2r").
    m = re.match(r"^([a-züê:v]+)([1-5])?(r?)$", (syl or "").lower())
    if not m or not m.group(1):
        return None
    body, tone, erhua = m.group(1), m.group(2), m.group(3)
    body = body.replace("u:", "ü").replace("v", "ü")
    if not tone or tone == "5":
        return body + erhua
    t = int(tone) - 1
    v = body
    if "a" in v:
        key, idx = "a", v.index("a")
    elif "e" in v:
        key, idx = "e", v.index("e")
    elif "ou" in v:
        key, idx = "o", v.index("o")
    elif "ü" in v:
        key, idx = "ü", v.index("ü")
    else:
        # mark the LAST vowel (iu->iù, ui->uì, ong->ōng)
        mm = None
        for mm in re.finditer(r"[aeiouü]", v):
            pass
        if mm is None:
            return body
        key, idx = mm.group(0), mm.start()
    marked = _TONE_MARKS.get(key, [key] * 4)[t] if key in _TONE_MARKS else key
    return v[:idx] + marked + v[idx + 1:] + erhua


def cedict_pinyin_to_diac(numbered: str):
    """Converts full CC-CEDICT pinyin ("ni3 hao3") to diacritics ("nǐ hǎo")."""
    out = []
    for syl in (numbered or "").strip().split():
        c = cedict_syllable_to_diac(syl)
        if c is None:
            return None
        out.append(c)
    return " ".join(out) if out else None


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

        # NFC first: the same syllable in NFD vs NFC compares unequal,
        # which would create duplicate rows and failed lookups.
        pinyin_text = unicodedata.normalize("NFC", pinyin_text)

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
    # Keyed by HANZI (not pinyin): homophones like 试 shì ("to test",
    # action verb, takes 了) must NOT inherit 是's stative templates.
    # The hanzi-less pinyin fallback keeps old direct calls working.
    COPULA_HANZI = {"是": "shi", "像": "xiang", "有": "you", "在": "zai"}
    STATIVE_RULES = {
        # copula/identity: no le/zài anywhere; past neg uses bù
        "shi":   {"past_aff": "", "past_neg": "bú ", "prog_aff": "",
                  "prog_neg": "bú ", "imp_aff": "yào ", "imp_neg": "bú yào "},
        "xiang": {"past_aff": "", "past_neg": "bú ", "prog_aff": "",
                  "prog_neg": "bú ", "imp_aff": "yào ", "imp_neg": "bú yào "},
        # possession: "yǒu le" OK, "méi yǒu" OK; only progressive is barred
        "you":   {"past_aff": " le", "past_neg": "méi ", "prog_aff": "",
                  "prog_neg": "méi ", "imp_aff": "yào ", "imp_neg": "bú yào "},
        # location: past neg "méi zài" OK; bare forms elsewhere (avoids
        # *"zài le" and *"zài zài")
        "zai":   {"past_aff": "", "past_neg": "méi ", "prog_aff": "",
                  "prog_neg": "méi ", "imp_aff": "yào ", "imp_neg": "bú yào "},
    }
    # Pinyin fallback for hanzi-less callers (tests, old code paths).
    STATIVE_PINYIN_FALLBACK = {"shì": "shi", "xiàng": "xiang",
                               "yǒu": "you", "zài": "zai"}

    def generate_full_paradigm(self, base_word: str, hanzi: str = ""):
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

        rule_key = self.COPULA_HANZI.get(hanzi or "")
        if rule_key is None and not hanzi:
            rule_key = self.STATIVE_PINYIN_FALLBACK.get(base_word)
        st = self.STATIVE_RULES.get(rule_key or "")
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
                        "meaning_en": raw_english_joined,
                        "hanzi": unicodedata.normalize(
                            "NFC", item.get("simplified", "")),
                    })
                except Exception:
                    pass
                    
            print(f"Success! Evaluating {len(words_data)} HSK words for verbs...")
            return words_data
        except Exception as e:
            print(f"Failed to fetch dataset: {e}")
            return []

    # Ultra-common verbs pinned against upstream loss: the HSK source is a
    # live file and entries vanish between rebuilds (e.g. 变成 dropped out
    # upstream). Pins carry their own glosses so a same-pinyin homophone
    # from CC-CEDICT (试 "to test") can never shadow the core sense
    # (是 "to be"). Pins already covered by HSK are skipped silently.
    # (pinyin, hanzi, gloss). Hanzi-keyed so homophones coexist: 是 "to be"
    # (stative templates) never collides with 试 "to test" (action templates).
    PINNED_CORE = [
        ("shì", "是", "to be"), ("chī", "吃", "to eat"), ("hē", "喝", "to drink"),
        ("qù", "去", "to go"), ("lái", "来", "to come"), ("kàn", "看", "to look"),
        ("tīng", "听", "to listen"), ("shuō", "说", "to speak"),
        ("dú", "读", "to read"), ("xiě", "写", "to write"),
        ("xué", "学", "to learn"), ("mǎi", "买", "to buy"),
        ("mài", "卖", "to sell"), ("kāi", "开", "to open"),
        ("guān", "关", "to close"), ("shuì", "睡", "to sleep"),
        ("qǐ", "起", "to rise"), ("pǎo", "跑", "to run"),
        ("zǒu", "走", "to walk"), ("fēi", "飞", "to fly"),
        ("xiào", "笑", "to laugh"), ("kū", "哭", "to cry"),
        ("zuò", "坐", "to sit"), ("zhàn", "站", "to stand"),
        ("zhù", "住", "to live"), ("gōngzuò", "工作", "to work"),
        ("xuéxí", "学习", "to study"), ("chīfàn", "吃饭", "to eat"),
        ("shuìjiào", "睡觉", "to sleep"), ("qǐchuáng", "起床", "to get up"),
        ("chànggē", "唱歌", "to sing"), ("tiàowǔ", "跳舞", "to dance"),
        ("kànshū", "看书", "to read"), ("xiězì", "写字", "to write"),
        ("tīng yīnyuè", "听音乐", "to listen to music"),
        ("shuōhuà", "说话", "to speak"), ("dúshū", "读书", "to study"),
        ("shàngbān", "上班", "to go to work"),
        ("xiàbān", "下班", "to get off work"),
        ("huíjiā", "回家", "to go home"),
        ("shàngxué", "上学", "to go to school"),
        ("zuòfàn", "做饭", "to cook"), ("xǐzǎo", "洗澡", "to bathe"),
        ("chuān", "穿", "to wear"), ("kāichē", "开车", "to drive"),
        ("guānmén", "关门", "to close the door"),
        ("mǎi dōngxi", "买东西", "to shop"),
        ("yóuyǒng", "游泳", "to swim"), ("pǎobù", "跑步", "to run"),
        ("zǒulù", "走路", "to walk"),
        ("biànchéng", "变成", "to change into"),
    ]

    def fetch_cedict_dataset(self, exclude: set) -> list:
        """Fetches CC-CEDICT (CC BY-SA 4.0, MDBG) and returns verb entries
        whose pinyin is not already covered. Budgets additions so the
        database stays shippable: all monosyllabic + all 3-syllable verbs,
        pinned core verbs, plus a STABLE hash sample of disyllabic verbs
        (hash sampling, unlike stride sampling, does not reshuffle when
        the pool grows between rebuilds)."""
        url = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        print("Fetching CC-CEDICT for verb expansion (CC BY-SA 4.0)...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx) as response:
                text = gzip.decompress(response.read()).decode("utf-8")
        except Exception as e:
            print(f"CC-CEDICT fetch failed ({e}); continuing with HSK only.")
            return []

        ones, twos, threes = [], [], []
        for line in text.split("\n"):
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^(\S+) (\S+) \[([^\]]+)\] (.*)$", line)
            if not m:
                continue
            pin = m.group(3)
            if re.search(r"[A-Z·]", pin):
                continue  # proper nouns, abbreviations
            first_to = ""
            for d in m.group(4).strip("/").split("/"):
                if d.strip().lower().startswith("to "):
                    first_to = d.strip()
                    break
            if not first_to:
                continue
            # Keep explicit sexual/bodily vulgarity out of a general lexicon
            # (e.g. 肛交 "to have anal intercourse"). Word-boundaried so
            # legit verbs like "to adulterate" survive.
            if re.search(r"\b(anal|masturbat\w*|orgasm\w*|ejaculat\w*|copulat\w*|"
                         r"sodom\w*|fellat\w*|cunniling\w*|bestial\w*|defecat\w*|"
                         r"urinat\w*|fornicat\w*|porn\w*|incest\w*)\b",
                         first_to, flags=re.IGNORECASE):
                continue
            dia = cedict_pinyin_to_diac(pin)
            if not dia:
                continue
            clean = self.sanitize_pinyin(dia)
            # FATAL FIX: group(1) is TRADITIONAL, group(2) is SIMPLIFIED.
            # Using group(1) stored 變成 for 变成, breaking pin matching
            # and mixing scripts. Simplified matches HSK convention.
            hz = unicodedata.normalize("NFC", m.group(2))
            if not clean or len(clean) <= 1 or (hz, clean) in exclude:
                continue
            syls = clean.split()
            if any(len(s) <= 1 for s in syls):
                continue  # letter-spellings like "c o s" (to cosplay)
            # Dedupe key includes hanzi: homophones (做/作 zuò) coexist.
            item = {"pinyin_raw": dia, "meaning_en": first_to, "hanzi": hz}
            if len(syls) == 1:
                ones.append(((hz, clean), item))
            elif len(syls) == 2:
                twos.append(((hz, clean), item))
            elif len(syls) == 3:
                threes.append(((hz, clean), item))
            # 4+ syllable entries skipped: mostly idioms; keeps DB shippable

        import hashlib
        # Pool deduped by (hanzi, pinyin) here.
        pool = {}
        for key, item in ones + threes + twos:
            pool.setdefault(key, item)
        # Pinned core verbs: exact (hanzi, pinyin) match, overriding gloss.
        # Pins are self-sufficient: if neither source carries the entry in
        # this snapshot (live sources flap), the pin is inserted directly
        # from curation instead of being skipped.
        pinned = []
        for pin_pinyin, pin_hanzi, pin_gloss in self.PINNED_CORE:
            if (pin_hanzi, pin_pinyin) in exclude:
                continue  # HSK already covers it
            hit = pool.get((pin_hanzi, pin_pinyin))
            if hit is None:
                hit = {"pinyin_raw": pin_pinyin, "meaning_en": pin_gloss,
                       "hanzi": pin_hanzi}
            else:
                hit = dict(hit)
                hit["meaning_en"] = pin_gloss
            pinned.append(hit)
        pinned_keys = {(pin_hanzi, pin_pinyin) for pin_pinyin, pin_hanzi, _ in self.PINNED_CORE}
        ones = [i for k, i in ones if k not in pinned_keys]
        threes = [i for k, i in threes if k not in pinned_keys]
        # Stable hash sample of the rest of the disyllabic verbs.
        sampled = []
        for (hz, clean), item in twos:
            if (hz, clean) in pinned_keys:
                continue
            if int(hashlib.sha1(clean.encode("utf-8")).hexdigest(), 16) % 100 < 15:
                sampled.append(item)
        chosen = pinned + ones + threes + sampled
        print(f"CC-CEDICT: {len(pinned)} pinned + {len(ones)} monosyllabic + "
              f"{len(threes)} 3-syllable + {len(sampled)} disyllabic (hash15) = "
              f"{len(chosen)} new verbs.")
        return chosen

    def _verb_key(self, item):
        """Returns ((hanzi, clean_pinyin), gloss) if the item is a usable
        verb, else None.

        FATAL FIX: the verb filter must run BEFORE dedup. Deduping raw
        pinyin first let a noun homophone (市 "market") shadow the verb
        (是 "to be") sharing its pinyin, silently deleting 是 from the DB.
        Dedup key includes hanzi so true homophones (做/作 zuò) coexist.
        """
        clean = self.sanitize_pinyin(item.get("pinyin_raw", ""))
        if not clean or len(clean) <= 1:
            return None
        gloss = self.format_english_definition(item.get("meaning_en", ""))
        if not gloss:
            return None
        hanzi = unicodedata.normalize(
            "NFC", item.get("hanzi", "") or "")
        return (hanzi, clean), gloss

    def build_database(self):
        dataset = self.fetch_hsk_dataset()

        seen = set()
        curated = []
        for item in dataset:
            key = self._verb_key(item)
            if key and key[0] not in seen:
                seen.add(key[0])
                curated.append(item)
        for item in self.fetch_cedict_dataset(seen):
            key = self._verb_key(item)
            if key and key[0] not in seen:
                seen.add(key[0])
                curated.append(item)
        dataset = curated
        if not dataset:
            print("No data loaded. Exiting build process.")
            return
        print(f"Combined lexicon: {len(dataset)} verbs (HSK first, then CC-CEDICT).")
        
        # NOTE: filename must match index.html loader (Sinitic/mandarin.sqlite).
        db_path = "mandarin.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")

        # Schema migration: hanzi column (homophone support) added after the
        # first builds. Old files without it are rebuilt from scratch.
        _cols = [r[1] for r in cursor.execute("PRAGMA table_info(verbs)")]
        if _cols and "hanzi" not in _cols:
            cursor.execute("DROP TABLE IF EXISTS conjugations")
            cursor.execute("DROP TABLE IF EXISTS nominals")
            cursor.execute("DROP TABLE IF EXISTS verbs")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verbs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_pinyin TEXT,
                hanzi TEXT DEFAULT "",
                sub_english TEXT,
                UNIQUE(base_pinyin, hanzi)
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

            hanzi = unicodedata.normalize(
                "NFC", item.get("hanzi", "") or "")

            try:
                cursor.execute("""
                    INSERT INTO verbs (base_pinyin, hanzi, sub_english)
                    VALUES (?, ?, ?)
                """, (base_pinyin, hanzi, formatted_english))
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

            # Generate and insert grammar conjugations (hanzi selects the
            # correct template family: 是 is stative, 试 is action).
            dialectal_conjugations = self.generate_full_paradigm(
                base_pinyin, hanzi)
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