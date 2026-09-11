import json
import sqlite3
import urllib.request
import urllib.parse
import ssl

# A meticulously curated core lexicon targeting Javanese verbs with extreme
# register suppletion. Automated scrapers miss that "turu" and "sare" are the
# same verb in different speech levels, so this acts as our absolute ground truth.
CORE_SUPPLETION_MAP = [
    {"ngoko": "pangan", "krama": "nedha", "ngapak": "madhang", "english": "to eat"},
    {"ngoko": "turu", "krama": "sare", "ngapak": "turu", "english": "to sleep"},
    {"ngoko": "lunga", "krama": "kesah", "ngapak": "lunga", "english": "to go"},
    {"ngoko": "teka", "krama": "rawuh", "ngapak": "teka", "english": "to come"},
    {"ngoko": "bali", "krama": "kondur", "ngapak": "bali", "english": "to return"},
    {"ngoko": "gawa", "krama": "bekta", "ngapak": "nggawa", "english": "to bring"},
    {"ngoko": "weneh", "krama": "paring", "ngapak": "wehna", "english": "to give"},
    {"ngoko": "tuku", "krama": "mundhut", "ngapak": "tuku", "english": "to buy"},
    {"ngoko": "ombe", "krama": "unjuk", "ngapak": "nginum", "english": "to drink"},
    {"ngoko": "deleng", "krama": "pirsa", "ngapak": "mirsani", "english": "to see"},
    {"ngoko": "krungu", "krama": "mireng", "ngapak": "krungu", "english": "to hear"},
    {"ngoko": "omong", "krama": "ngendika", "ngapak": "omong", "english": "to speak"},
    {"ngoko": "waca", "krama": "waos", "ngapak": "waca", "english": "to read"},
    {"ngoko": "tulis", "krama": "serat", "ngapak": "tulis", "english": "to write"},
    {"ngoko": "kongkon", "krama": "utus", "ngapak": "kongkon", "english": "to command"},
    {"ngoko": "lungguh", "krama": "pinarak", "ngapak": "jijag", "english": "to sit"},
    {"ngoko": "ngadeg", "krama": "jumeneng", "ngapak": "ngadeg", "english": "to stand"},
    {"ngoko": "gawe", "krama": "damel", "ngapak": "gawe", "english": "to make"},
    {"ngoko": "jaluk", "krama": "suwun", "ngapak": "jaluk", "english": "to ask for"},
    {"ngoko": "ngerti", "krama": "ngertos", "ngapak": "ngerti", "english": "to understand"},
    {"ngoko": "kandha", "krama": "criyos", "ngapak": "kandha", "english": "to tell"},
    {"ngoko": "duwe", "krama": "kagungan", "ngapak": "duwe", "english": "to have"},
    {"ngoko": "mati", "krama": "seda", "ngapak": "mati", "english": "to die"},
    {"ngoko": "urip", "krama": "gesang", "ngapak": "urip", "english": "to live"},
    {"ngoko": "adus", "krama": "siram", "ngapak": "adus", "english": "to bathe"},
    {"ngoko": "pikir", "krama": "penggalih", "ngapak": "pikir", "english": "to think"},
    {"ngoko": "jupuk", "krama": "pundhut", "ngapak": "jupuk", "english": "to take"},
    {"ngoko": "adol", "krama": "sade", "ngapak": "adol", "english": "to sell"},
    {"ngoko": "takon", "krama": "dangu", "ngapak": "takon", "english": "to ask a question"},
    {"ngoko": "undang", "krama": "timbal", "ngapak": "undang", "english": "to call"},
    {"ngoko": "golek", "krama": "pados", "ngapak": "golek", "english": "to seek"},
    {"ngoko": "eling", "krama": "emut", "ngapak": "eling", "english": "to remember"},
    {"ngoko": "seneng", "krama": "remen", "ngapak": "seneng", "english": "to like"},
    {"ngoko": "jaga", "krama": "reksa", "ngapak": "jaga", "english": "to guard"},
    {"ngoko": "mlaku", "krama": "mlampah", "ngapak": "mlaku", "english": "to walk"},
    {"ngoko": "nunggang", "krama": "nitih", "ngapak": "nunggang", "english": "to ride"},
    {"ngoko": "mudhun", "krama": "mandhap", "ngapak": "mudhun", "english": "to descend"},
    {"ngoko": "munggah", "krama": "minggah", "ngapak": "munggah", "english": "to ascend"},
    {"ngoko": "silih", "krama": "ngampil", "ngapak": "silih", "english": "to borrow"},
    {"ngoko": "gebug", "krama": "gebug", "ngapak": "gebug", "english": "to hit"},
    {"ngoko": "bayar", "krama": "bayar", "ngapak": "bayar", "english": "to pay"},
    {"ngoko": "coba", "krama": "cobi", "ngapak": "jajal", "english": "to try"},
    {"ngoko": "buka", "krama": "bikak", "ngapak": "buka", "english": "to open"},
    {"ngoko": "tutup", "krama": "tutup", "ngapak": "tutup", "english": "to close"},
    {"ngoko": "kumbah", "krama": "kumbah", "ngapak": "kumbah", "english": "to wash"},
    {"ngoko": "sapu", "krama": "sapu", "ngapak": "sapu", "english": "to sweep"},
    {"ngoko": "cukur", "krama": "pangkas", "ngapak": "cukur", "english": "to shave"},
    {"ngoko": "ganti", "krama": "gantos", "ngapak": "ganti", "english": "to change"},
    {"ngoko": "ilang", "krama": "ical", "ngapak": "ilang", "english": "to lose"},
    {"ngoko": "oleh", "krama": "pikantuk", "ngapak": "entuk", "english": "to get/obtain"}
]


class JavanesePhonologyEngine:
    @staticmethod
    def active_nasal(root: str) -> str:
        """
        Applies the Javanese active nasal prefix (Ater-ater Anuswara: N-).
        Automatically maps morphological shifts according to orthographic rules.
        """
        w = root.lower().strip()
        if not w: return ""
        
        # Protect digraphs first
        if w.startswith('dh'): return 'n' + w        # dhesek -> ndhesek
        if w.startswith('th'): return 'n' + w[2:]    # thuthuk -> nuthuk
        if w.startswith('ng') or w.startswith('ny'): return w
        
        c = w[0]
        if c == 'p': return 'm' + w[1:]              # pangan -> mangan
        if c == 'b': return 'm' + w                  # bakar -> mbakar
        if c == 't': return 'n' + w[1:]              # tulis -> nulis
        if c == 'd': return 'n' + w                  # deleng -> ndeleng
        if c in ('c', 's'): return 'ny' + w[1:]      # sapu -> nyapu
        if c == 'j': return 'n' + w                  # jupuk -> njupuk
        if c == 'k': return 'ng' + w[1:]             # kethok -> ngethok
        if c == 'g': return 'ng' + w                 # guyu -> ngguyu
        if c == 'w': return 'm' + w[1:]              # waca -> maca
        if c in ('a', 'e', 'i', 'o', 'u'): return 'ng' + w  # ombe -> ngombe
        if c in ('l', 'r', 'y'): return 'ng' + w     # lamar -> nglamar
        if c in ('m', 'n'): return w
        
        return 'ng' + w


class JavanesePipeline:
    def __init__(self):
        self.dialects = [
            {"code": "ngoko_lugu", "name": "Ngoko Lugu (Standard Informal)"},
            {"code": "krama_lugu", "name": "Krama Lugu (Standard Formal)"},
            {"code": "surabayan", "name": "Surabayan (Arekan/East Java)"},
            {"code": "banyumasan", "name": "Banyumasan (Ngapak)"}
        ]
        
        self.persons = [
            {"id": "1s", "p": "1", "n": "sg"},
            {"id": "2s", "p": "2", "n": "sg"},
            {"id": "3s", "p": "3", "n": "sg"},
            {"id": "1p", "p": "1", "n": "pl"},
            {"id": "2p", "p": "2", "n": "pl"},
            {"id": "3p", "p": "3", "n": "pl"}
        ]
        
        self.imperative_persons = [
            {"id": "2s", "p": "2", "n": "sg"},
            {"id": "2p", "p": "2", "n": "pl"}
        ]
        
        self.pronouns_map = {
            "ngoko_lugu": {"1s": "aku", "2s": "kowe", "3s": "dheweke", "1p": "awake dhewe", "2p": "kowe kabeh", "3p": "dheweke kabeh"},
            "krama_lugu": {"1s": "kula", "2s": "panjenengan", "3s": "piyambakipun", "1p": "kula sedaya", "2p": "panjenengan sedaya", "3p": "piyambakipun sedaya"},
            "surabayan": {"1s": "aku", "2s": "koen", "3s": "de'e", "1p": "awake dhewe", "2p": "koen kabeh", "3p": "de'e kabeh"},
            "banyumasan": {"1s": "inyong", "2s": "rika", "3s": "deweke", "1p": "dewek", "2p": "rika pada", "3p": "deweke pada"}
        }

    def fetch_wiktionary_verbs(self):
        """
        Deep scraping engine: Automatically paginates through Wiktionary 
        to dump every available Javanese verb root dynamically.
        """
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        print("Deep scraping Javanese verbs from Wiktionary API...")
        url = "https://en.wiktionary.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Javanese_verbs&cmlimit=500&format=json"
        
        scraped_verbs = []
        while url:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'OpenWorldDialects/1.0'})
                with urllib.request.urlopen(req, context=ctx) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                for member in data.get('query', {}).get('categorymembers', []):
                    title = member.get('title', '')
                    # Isolate pure roots (discard prefixes, romanizations, or script variants)
                    if ":" not in title and len(title) > 2 and title.isascii() and " " not in title and "-" not in title:
                        title = title.lower()
                        scraped_verbs.append({
                            "ngoko": title,
                            "krama": title,
                            "ngapak": title,
                            "english": "to " + title
                        })
                
                if 'continue' in data and 'cmcontinue' in data['continue']:
                    cmcontinue = urllib.parse.quote(data['continue']['cmcontinue'])
                    url = f"https://en.wiktionary.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Javanese_verbs&cmlimit=500&cmcontinue={cmcontinue}&format=json"
                else:
                    url = None
            except Exception as e:
                print("Wiktionary scrape failed:", e)
                break
                
        print(f"Successfully deep-scraped {len(scraped_verbs)} verbs from Wiktionary.")
        return scraped_verbs

    def generate_full_paradigm(self, item):
        ngoko_act = JavanesePhonologyEngine.active_nasal(item["ngoko"])
        krama_act = JavanesePhonologyEngine.active_nasal(item["krama"])
        ngapak_act = JavanesePhonologyEngine.active_nasal(item["ngapak"])
        
        templates = {
            "ngoko_lugu": {
                "root": item["ngoko"], "act": ngoko_act,
                "past": {"aff": "{p} wis {v}", "neg": "{p} durung {v}"},
                "present": {"aff": "{p} lagi {v}", "neg": "{p} ora {v}"},
                "future": {"aff": "{p} arep {v}", "neg": "{p} ora arep {v}"},
                "progressive": {"aff": "{p} isih {v}", "neg": "{p} wis ora {v}"},
                "imperative": {"aff": "ayo {v}!", "neg": "aja {v}!"}
            },
            "krama_lugu": {
                "root": item["krama"], "act": krama_act,
                "past": {"aff": "{p} sampun {v}", "neg": "{p} dereng {v}"},
                "present": {"aff": "{p} nembe {v}", "neg": "{p} mboten {v}"},
                "future": {"aff": "{p} badhe {v}", "neg": "{p} mboten badhe {v}"},
                "progressive": {"aff": "{p} taksih {v}", "neg": "{p} sampun mboten {v}"},
                "imperative": {"aff": "mangga {v}", "neg": "ampun {v}"}
            },
            "surabayan": {
                "root": item["ngoko"], "act": ngoko_act,
                "past": {"aff": "{p} wis {v}", "neg": "{p} durung {v}"},
                "present": {"aff": "{p} lagi {v}", "neg": "{p} gak {v}"},
                "future": {"aff": "{p} kate {v}", "neg": "{p} gak kate {v}"},
                "progressive": {"aff": "{p} sik {v}", "neg": "{p} wis gak {v}"},
                "imperative": {"aff": "{v}o!", "neg": "ojok {v}!"}
            },
            "banyumasan": {
                "root": item["ngapak"], "act": ngapak_act,
                "past": {"aff": "{p} wis {v}", "neg": "{p} urung {v}"},
                "present": {"aff": "{p} lagi {v}", "neg": "{p} ora {v}"},
                "future": {"aff": "{p} pan {v}", "neg": "{p} ora pan {v}"},
                "progressive": {"aff": "{p} esih {v}", "neg": "{p} wis ora {v}"},
                "imperative": {"aff": "{v}a!", "neg": "aja {v}!"}
            }
        }
        
        dialect_conjugations = {}
        for code, gram in templates.items():
            aspects_data = {}
            v_act = gram["act"]
            
            for aspect in ["past", "present", "future", "progressive"]:
                aff_dict, neg_dict = {}, {}
                for p_data in self.persons:
                    pid = p_data["id"]
                    p = self.pronouns_map[code][pid]
                    aff_dict[pid] = gram[aspect]["aff"].format(p=p, v=v_act)
                    neg_dict[pid] = gram[aspect]["neg"].format(p=p, v=v_act)
                aspects_data[aspect] = {"affirmative": aff_dict, "negative": neg_dict}
            
            imp_aff, imp_neg = {}, {}
            for p_data in self.imperative_persons:
                pid = p_data["id"]
                # Syntactic shift logic for imperative depending on sub-dialect
                if code == "surabayan": cmd = f"{v_act}o"
                elif code == "banyumasan": cmd = f"{v_act}a"
                elif code == "ngoko_lugu": cmd = f"ayo {v_act}"
                else: cmd = f"mangga {v_act}"
                
                imp_aff[pid] = cmd
                imp_neg[pid] = gram["imperative"]["neg"].format(v=v_act)
                
            aspects_data["imperative"] = {"affirmative": imp_aff, "negative": imp_neg}
            dialect_conjugations[code] = aspects_data
            
        return dialect_conjugations

    def generate_nominals(self, item):
        n_act = JavanesePhonologyEngine.active_nasal(item["ngoko"])
        
        return {
            "infinitive": {
                "affirmative": {"phrase": n_act},
                "negative": {"phrase": f"ora {n_act}"}
            },
            "passive_participle": {
                "affirmative": {"phrase": f"di{item['ngoko']}"},
                "negative": {"phrase": f"ora di{item['ngoko']}"}
            },
            "doer_masculine_sg": {
                "affirmative": {"phrase": f"sing {n_act}"},
                "negative": {"phrase": f"sing ora {n_act}"}
            },
            "masdar": {
                "affirmative": {"phrase": f"anggone {n_act}"},
                "negative": {"phrase": f"anggone ora {n_act}"}
            }
        }

    def build_database(self):
        # Merge Curated Lexicon with deeply scraped Wiktionary pool
        dataset = CORE_SUPPLETION_MAP.copy()
        scraped = self.fetch_wiktionary_verbs()
        
        seen = {v["ngoko"] for v in dataset}
        for sv in scraped:
            if sv["ngoko"] not in seen:
                dataset.append(sv)
                seen.add(sv["ngoko"])
        
        db_path = "javanese.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("CREATE TABLE IF NOT EXISTS roots (id INTEGER PRIMARY KEY AUTOINCREMENT, base_root TEXT UNIQUE, meaning_english TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS nominals (id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, category TEXT, polarity TEXT, phrase TEXT, FOREIGN KEY(root_id) REFERENCES roots(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS conjugations (id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, dialect TEXT, aspect TEXT, polarity TEXT, person_id TEXT, person TEXT, number TEXT, phrase TEXT, FOREIGN KEY(root_id) REFERENCES roots(id))")

        cursor.execute("DELETE FROM conjugations")
        cursor.execute("DELETE FROM nominals")
        cursor.execute("DELETE FROM roots")

        for item in dataset:
            try:
                cursor.execute("INSERT INTO roots (base_root, meaning_english) VALUES (?, ?)", (item["ngoko"], item["english"]))
                root_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                continue

            nominals = self.generate_nominals(item)
            nom_tuples = []
            for n_type, polarities in nominals.items():
                for pol, scripts in polarities.items():
                    nom_tuples.append((root_id, n_type, pol, scripts["phrase"]))
            
            cursor.executemany("INSERT INTO nominals (root_id, category, polarity, phrase) VALUES (?, ?, ?, ?)", nom_tuples)

            dialectal_conjugations = self.generate_full_paradigm(item)
            conj_tuples = []
            for d in self.dialects:
                d_code = d["code"]
                for aspect, pol_dict in dialectal_conjugations[d_code].items():
                    for pol, persons_dict in pol_dict.items():
                        for pid, phrase in persons_dict.items():
                            p_info = next((x for x in self.persons if x["id"] == pid), None)
                            if not p_info:
                                p_info = next((x for x in self.imperative_persons if x["id"] == pid))
                            conj_tuples.append((root_id, d_code, aspect, pol, pid, p_info["p"], p_info["n"], phrase))

            cursor.executemany("INSERT INTO conjugations (root_id, dialect, aspect, polarity, person_id, person, number, phrase) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", conj_tuples)

        conn.commit()
        conn.close()
        print(f"Javanese Syntactic Database Generated Successfully: '{db_path}'")

if __name__ == "__main__":
    pipeline = JavanesePipeline()
    pipeline.build_database()