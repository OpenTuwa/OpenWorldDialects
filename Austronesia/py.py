import json
import re
import ssl
import sqlite3
import urllib.error
import urllib.request


class MalayPhonologyEngine:
    """
    Advanced morphophonemic and phonological transformer for Malay dialects.
    Applies authentic, regional speech rules to base roots.
    """
    
    @staticmethod
    def standard_prefix(prefix_type: str, root: str) -> str:
        """Applies Standard Malay Imbuhan (MeN- / PeN-) rules."""
        if not root: return ""
        first = root[0]
        if len(root) <= 3 and root not in ['ada', 'apa', 'air']: return f"m{'enge' if prefix_type == 'me' else 'penge'}{root}"
        if first in ['l', 'm', 'n', 'r', 'w', 'y']: return f"m{'e' if prefix_type == 'me' else 'pe'}{root}"
        if first in ['b', 'f', 'v']: return f"m{'em' if prefix_type == 'me' else 'pem'}{root}"
        if first == 'p': return f"m{'em' if prefix_type == 'me' else 'pem'}{root[1:]}" # Drop P
        if first in ['c', 'd', 'j', 'z']: return f"m{'en' if prefix_type == 'me' else 'pen'}{root}"
        if first == 't': return f"m{'en' if prefix_type == 'me' else 'pen'}{root[1:]}" # Drop T
        if first in ['a', 'e', 'i', 'o', 'u', 'g', 'h']: return f"m{'eng' if prefix_type == 'me' else 'peng'}{root}"
        if first == 'k': return f"m{'eng' if prefix_type == 'me' else 'peng'}{root[1:]}" # Drop K
        if first == 's': return f"m{'eny' if prefix_type == 'me' else 'peny'}{root[1:]}" # Drop S
        return f"m{'e' if prefix_type == 'me' else 'pe'}{root}"

    @staticmethod
    def colloquial_nasalization(root: str) -> str:
        """
        Authentic Klang Valley / Colloquial mutation. 
        Drops 'me-' but retains the active nasal mutation for specific consonants.
        (e.g., pukul -> mukul, pancing -> mancing, tulis -> nulis).
        """
        first = root[0]
        if first == 'p': return 'm' + root[1:]
        if first == 't': return 'n' + root[1:]
        if first == 'k': return 'ng' + root[1:]
        if first == 's': return 'ny' + root[1:]
        if first == 'c': return 'ny' + root[1:] # e.g., curi -> nyuri
        return root # If no mutation, return base (e.g., bincang -> bincang)

    @staticmethod
    def kelantan_shift(root: str) -> str:
        """Kelantanese phonological shifts."""
        w = root.lower()
        w = re.sub(r'(an|am|ang)$', 'e', w) # bincang -> bince, makan -> make
        w = re.sub(r'a$', 'o', w)           # buka -> buko
        w = re.sub(r's$', 'h', w)           # malas -> malah
        w = re.sub(r'ar$', 'o', w)          # lapar -> lapo
        w = re.sub(r'r$', '', w)            # dengar -> denga
        return w

    @staticmethod
    def terengganu_shift(root: str) -> str:
        """Terengganuan phonological shifts."""
        w = root.lower()
        w = re.sub(r'a$', 'e', w)           # buka -> buke
        w = re.sub(r'([mn])$', 'ng', w)     # makan -> makang, malam -> malang
        w = re.sub(r'r$', '', w)
        return w

    @staticmethod
    def kedah_shift(root: str) -> str:
        """Kedahan phonological shifts."""
        w = root.lower()
        w = re.sub(r'r$', 'q', w)           # lapar -> lapaq, dengar -> dengaq
        w = re.sub(r'as$', 'aih', w)        # lepas -> lepaih
        w = re.sub(r'is$', 'ih', w)         # manis -> manih
        return w


class MalayLicensedRootPipeline:
    def __init__(self):
        self.phonology = MalayPhonologyEngine()
        
        self.dialects = [
            {"code": "standard", "name": "Bahasa Melayu Standard"},
            {"code": "colloquial", "name": "Colloquial / Urban"},
            {"code": "kelantanese", "name": "Baso Kelate"},
            {"code": "terengganuan", "name": "Base Tranung"},
            {"code": "kedahan", "name": "Pelat Utara"},
            {"code": "perakian", "name": "Loghat Perak"},
            {"code": "minang_n9", "name": "Bahasa Nogori"},
            {"code": "sarawakian", "name": "Bahasa Sarawak"},
            {"code": "sabahan", "name": "Bahasa Sabah"}
        ]

        self.persons = [
            {"id": "1s", "p": "1", "n": "sg"},
            {"id": "2s", "p": "2", "n": "sg"},
            {"id": "3s", "p": "3", "n": "sg"},
            {"id": "1p", "p": "1", "n": "pl"},
            {"id": "2p", "p": "2", "n": "pl"},
            {"id": "3p", "p": "3", "n": "pl"},
        ]
        self.imperative_persons = [{"id": "2s", "p": "2", "n": "sg"}, {"id": "2p", "p": "2", "n": "pl"}]

    def sanitize_root(self, root_text: str) -> str:
        return re.sub(r"[^a-zA-Z\s]", "", root_text.lower()).strip() if root_text else ""

    def generate_full_paradigm(self, root: str):
        """
        Massive syntactic matrix. Instead of naive concatenation, this uses 
        strict contextual templates so phrases sound like real native speech.
        """
        
        # 1. Phonologically process the verb for each state
        verb_std = self.phonology.standard_prefix("me", root)
        verb_coll = self.phonology.colloquial_nasalization(root)
        verb_kel = self.phonology.kelantan_shift(root)
        verb_ter = self.phonology.terengganu_shift(root)
        verb_ked = self.phonology.kedah_shift(root)
        verb_base = root

        # 2. Syntax mapping: [Dialect][Aspect][Polarity] -> Phrase Template
        templates = {
            "standard": {
                "verb": verb_std,
                "pronouns": {"1s": "saya", "2s": "awak", "3s": "dia", "1p": "kami", "2p": "kalian", "3p": "mereka"},
                "past": {"aff": "{p} telah {v}", "neg": "{p} belum {v}"},
                "present": {"aff": "{p} sedang {v}", "neg": "{p} tidak {v}"},
                "future": {"aff": "{p} akan {v}", "neg": "{p} tidak akan {v}"},
                "progressive": {"aff": "{p} masih {v}", "neg": "{p} sudah tidak {v}"},
                "imperative": {"aff": "{p}, sila {v}", "neg": "{p}, jangan {v}"}
            },
            "colloquial": {
                "verb": verb_coll,
                "pronouns": {"1s": "aku", "2s": "kau", "3s": "dia", "1p": "kita orang", "2p": "korang", "3p": "diorang"},
                "past": {"aff": "{p} dah {v}", "neg": "{p} belum {v} lagi"},
                "present": {"aff": "{p} tengah {v}", "neg": "{p} tak {v} pun"},
                "future": {"aff": "{p} nak {v}", "neg": "{p} tak nak {v}"},
                "progressive": {"aff": "{p} duk {v}", "neg": "{p} dah tak {v}"},
                "imperative": {"aff": "{p} pi {v}", "neg": "tak payah {v}, {p}"}
            },
            "kelantanese": {
                "verb": verb_kel,
                "pronouns": {"1s": "ambo", "2s": "demo", "3s": "dio", "1p": "kito", "2p": "demo", "3p": "puok dio"},
                "past": {"aff": "{p} doh {v}", "neg": "{p} tok {v} lagi"},
                "present": {"aff": "{p} loni duk {v}", "neg": "{p} tok {v}"},
                "future": {"aff": "{p} nok {v}", "neg": "{p} tokse {v}"},
                "progressive": {"aff": "{p} tgh duk {v}", "neg": "{p} tok {v} doh"},
                "imperative": {"aff": "{p} {v} la", "neg": "toksoh {v} la {p}"}
            },
            "terengganuan": {
                "verb": verb_ter,
                "pronouns": {"1s": "aku", "2s": "mung", "3s": "ye", "1p": "kite", "2p": "mung", "3p": "puok ye"},
                "past": {"aff": "{p} doh {v}", "neg": "{p} dok {v} agi"},
                "present": {"aff": "{p} duk {v}", "neg": "{p} dok {v}"},
                "future": {"aff": "{p} nok {v}", "neg": "{p} dok rok {v}"},
                "progressive": {"aff": "{p} duk {v} lagi", "neg": "{p} dok {v} doh"},
                "imperative": {"aff": "{p} g {v}", "neg": "doksoh {v}, {p}"}
            },
            "kedahan": {
                "verb": verb_ked,
                "pronouns": {"1s": "cek", "2s": "hang", "3s": "dia", "1p": "kami", "2p": "ampa", "3p": "depa"},
                "past": {"aff": "{p} dah {v}", "neg": "{p} tak {v} lagi"},
                "present": {"aff": "{p} tengah {v}", "neg": "{p} tak {v}"},
                "future": {"aff": "{p} nak {v}", "neg": "{p} tak mau {v}"},
                "progressive": {"aff": "{p} duk {v}", "neg": "{p} tak {v} dah"},
                "imperative": {"aff": "p {v}, {p}", "neg": "tak yah {v} la {p}"}
            },
            "perakian": {
                "verb": root, # Base verb generally used
                "pronouns": {"1s": "teman", "2s": "mika", "3s": "dia", "1p": "kome", "2p": "kome", "3p": "diorang"},
                "past": {"aff": "{p} dah {v}", "neg": "{p} belum {v}"},
                "present": {"aff": "{p} tengah {v}", "neg": "{p} tak {v}"},
                "future": {"aff": "{p} nak {v}", "neg": "{p} tak nak {v}"},
                "progressive": {"aff": "{p} duk {v}", "neg": "{p} tak {v} lagi"},
                "imperative": {"aff": "{p} {v} la", "neg": "tak payah {v} la {p}"}
            },
            "minang_n9": {
                "verb": verb_base,
                "pronouns": {"1s": "den", "2s": "ekau", "3s": "eyo", "1p": "kito", "2p": "kau orang", "3p": "urang tu"},
                "past": {"aff": "{p} dah {v}", "neg": "{p} alun {v} lai"},
                "present": {"aff": "{p} tangah {v}", "neg": "{p} tak {v} do"},
                "future": {"aff": "{p} nak {v}", "neg": "{p} tak nak {v}"},
                "progressive": {"aff": "{p} masih {v}", "neg": "{p} tak {v} la"},
                "imperative": {"aff": "{p} {v} la", "neg": "usah {v} la {p}"}
            },
            "sarawakian": {
                "verb": verb_base,
                "pronouns": {"1s": "kamek", "2s": "kitak", "3s": "nya", "1p": "kamek org", "2p": "kitak org", "3p": "sida"},
                "past": {"aff": "{p} dah {v}", "neg": "{p} alum {v}"},
                "present": {"aff": "{p} tengah {v}", "neg": "{p} sik {v}"},
                "future": {"aff": "{p} mok {v}", "neg": "{p} sik mok {v}"},
                "progressive": {"aff": "{p} agik {v}", "neg": "{p} sik {v} lagik"},
                "imperative": {"aff": "{p} {v} lok", "neg": "iboh {v} {p}"}
            },
            "sabahan": {
                "verb": verb_base,
                "pronouns": {"1s": "sia", "2s": "ko", "3s": "dia", "1p": "kami", "2p": "kamu", "3p": "dorang"},
                "past": {"aff": "{p} sudah {v}", "neg": "{p} balum {v}"},
                "present": {"aff": "{p} sadang {v}", "neg": "{p} ndak {v}"},
                "future": {"aff": "{p} mau {v}", "neg": "{p} ndak mau {v}"},
                "progressive": {"aff": "{p} masih {v}", "neg": "{p} ndak sudah {v}"},
                "imperative": {"aff": "{p} p {v}", "neg": "jangan {v} bah {p}"}
            }
        }

        dialect_conjugations = {}

        for code, grammar in templates.items():
            aspects_data = {}
            v = grammar["verb"]

            # Loop standard aspects
            for aspect in ["past", "present", "future", "progressive"]:
                aff_dict, neg_dict = {}, {}
                
                for p_data in self.persons:
                    pid = p_data["id"]
                    p = grammar["pronouns"][pid]
                    
                    # Fill the syntax template (e.g. "{p} belum {v} lagi")
                    aff_dict[pid] = grammar[aspect]["aff"].format(p=p, v=v)
                    neg_dict[pid] = grammar[aspect]["neg"].format(p=p, v=v)
                
                aspects_data[aspect] = {"affirmative": aff_dict, "negative": neg_dict}

            # Loop imperatives
            imp_aff, imp_neg = {}, {}
            for p_data in self.imperative_persons:
                pid = p_data["id"]
                p = grammar["pronouns"][pid]
                
                imp_aff[pid] = grammar["imperative"]["aff"].format(p=p, v=v)
                imp_neg[pid] = grammar["imperative"]["neg"].format(p=p, v=v)
                
            aspects_data["imperative"] = {"affirmative": imp_aff, "negative": imp_neg}
            dialect_conjugations[code] = aspects_data

        return dialect_conjugations

    def fetch_open_source_dataset(self) -> list:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        print("Fetching open-source English verb list for strict POS filtering...")
        verb_url = "https://raw.githubusercontent.com/dariusk/corpora/master/data/words/verbs.json"
        req_verbs = urllib.request.Request(verb_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_verbs, context=ctx) as response:
            verb_data = json.loads(response.read().decode("utf-8"))
            valid_english_verbs = {v["present"].lower() for v in verb_data.get("verbs", [])}

        dict_url = "https://dl.fbaipublicfiles.com/arrival/dictionaries/en-ms.txt"
        print(f"Fetching live dictionary from FB MUSE: {dict_url} ...")
        req_dict = urllib.request.Request(dict_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_dict, context=ctx) as response:
            data = response.read().decode("utf-8").strip().split("\n")

        print("Intersecting datasets and processing pure roots...")
        malay_dict = {}
        for line in data:
            parts = line.strip().split()
            if len(parts) == 2:
                en_w, ms_w = parts[0].lower(), parts[1].lower()
                
                if en_w in valid_english_verbs and ms_w != en_w:
                    if ms_w.isalpha() and 3 <= len(ms_w) <= 8:
                        if ms_w not in malay_dict: malay_dict[ms_w] = []
                        if en_w not in malay_dict[ms_w]: malay_dict[ms_w].append(en_w)

        roots_data = []
        for ms_word, en_meanings in list(malay_dict.items())[:2000]:
            meaning_str = "to " + " or ".join(en_meanings[:3])
            roots_data.append({"root": ms_word, "meaning_en": meaning_str})

        print(f"Successfully filtered {len(roots_data)} verified roots.")
        return roots_data

    def build_database(self):
        dataset = self.fetch_open_source_dataset()
        db_path = "master_malay_roots_backend.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("CREATE TABLE IF NOT EXISTS roots (id INTEGER PRIMARY KEY AUTOINCREMENT, base_root TEXT UNIQUE, meaning_english TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS conjugations (id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, dialect TEXT, aspect TEXT, polarity TEXT, person_id TEXT, person TEXT, number TEXT, phrase TEXT, FOREIGN KEY(root_id) REFERENCES roots(id))")
        
        cursor.execute("DELETE FROM conjugations")
        cursor.execute("DELETE FROM roots")

        for item in dataset:
            base_root = self.sanitize_root(item.get("root", ""))
            raw_english = item.get("meaning_en", "")
            if not base_root: continue
            
            try:
                cursor.execute("INSERT INTO roots (base_root, meaning_english) VALUES (?, ?)", (base_root, raw_english))
                root_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                continue

            # Core Generation
            dialectal_conjugations = self.generate_full_paradigm(base_root)
            conj_tuples = []
            
            for d in self.dialects:
                d_code = d["code"]
                d_conjugations = dialectal_conjugations.get(d_code, {})
                for aspect, pol_dict in d_conjugations.items():
                    for pol, persons_dict in pol_dict.items():
                        for pid, phrase in persons_dict.items():
                            p_info = next((x for x in self.persons if x["id"] == pid), None)
                            if not p_info: p_info = next((x for x in self.imperative_persons if x["id"] == pid))
                            
                            conj_tuples.append((root_id, d_code, aspect, pol, pid, p_info["p"], p_info["n"], phrase))

            cursor.executemany("INSERT INTO conjugations (root_id, dialect, aspect, polarity, person_id, person, number, phrase) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", conj_tuples)

        conn.commit()
        conn.close()
        print(f"Massive Dataset Built: 'master_malay_roots_backend.sqlite'")


if __name__ == "__main__":
    pipeline = MalayLicensedRootPipeline()
    pipeline.build_database()