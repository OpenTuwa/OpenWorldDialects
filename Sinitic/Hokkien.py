import json
import re
import ssl
import sqlite3
import urllib.request
import urllib.parse

# A robust core lexicon to anchor the dataset. NLP models and regex scrapers 
# occasionally miss extreme irregulars or multi-character compounds on Wiktionary. 
# This guarantees foundational conversational verbs are perfect, while the scraper handles the rest.
CORE_HOKKIEN_VERBS = [
    {"hanzi": "食", "poj": "chia̍h", "english": "to eat"},
    {"hanzi": "啉", "poj": "lim", "english": "to drink"},
    {"hanzi": "去", "poj": "khì", "english": "to go"},
    {"hanzi": "來", "poj": "lâi", "english": "to come"},
    {"hanzi": "看", "poj": "khòaⁿ", "english": "to look, to see"},
    {"hanzi": "聽", "poj": "thiaⁿ", "english": "to listen, to hear"},
    {"hanzi": "講", "poj": "kóng", "english": "to speak, to say"},
    {"hanzi": "寫", "poj": "siá", "english": "to write"},
    {"hanzi": "買", "poj": "bé", "english": "to buy"},
    {"hanzi": "賣", "poj": "bē", "english": "to sell"},
    {"hanzi": "行", "poj": "kiâⁿ", "english": "to walk"},
    {"hanzi": "走", "poj": "cháu", "english": "to run, to flee"},
    {"hanzi": "做", "poj": "chò", "english": "to do, to make"},
    {"hanzi": "想", "poj": "siūⁿ", "english": "to think"},
    {"hanzi": "知影", "poj": "chai-iáⁿ", "english": "to know"},
    {"hanzi": "愛", "poj": "ài", "english": "to love, to want"},
    {"hanzi": "睏", "poj": "khùn", "english": "to sleep"},
    {"hanzi": "徛", "poj": "khiā", "english": "to stand"},
    {"hanzi": "坐", "poj": "chē", "english": "to sit"},
    {"hanzi": "有", "poj": "ū", "english": "to have"},
    {"hanzi": "是", "poj": "sī", "english": "to be"},
    {"hanzi": "拍", "poj": "phah", "english": "to hit, to beat"},
    {"hanzi": "笑", "poj": "chhiò", "english": "to laugh"},
    {"hanzi": "哭", "poj": "khàu", "english": "to cry"},
    {"hanzi": "揣", "poj": "chhoē", "english": "to search, to look for"},
    {"hanzi": "等", "poj": "táng", "english": "to wait"}
]

class HokkienPipeline:
    def __init__(self):
        self.dialects = [
            {"code": "taiwanese", "name": "Taiwanese Hokkien (Tai-yu)"},
            {"code": "amoy", "name": "Amoy / Xiamen Hokkien"},
            {"code": "penang", "name": "Penang Hokkien (Malaysia)"}
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

    def deep_scrape_wiktionary(self):
        """
        Executes a deep web scrape of the Wiktionary API.
        Extracts Hanzi titles from 'Category:Min_Nan_verbs', then downloads their 
        underlying Wikitext revisions to surgically extract Pe̍h-ōe-jī (POJ) romanization 
        and clean English glosses using regex.
        """
        print("Initiating deep API scrape of Wiktionary for Hokkien (Min Nan) verbs...")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        scraped_verbs = []
        
        # Step 1: Get pages in the Min Nan verbs category
        list_url = "https://en.wiktionary.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Min_Nan_verbs&cmlimit=300&format=json"
        
        try:
            req = urllib.request.Request(list_url, headers={'User-Agent': 'OpenWorldDialects/1.0'})
            with urllib.request.urlopen(req, context=ctx) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            members = data.get('query', {}).get('categorymembers', [])
            titles = [m['title'] for m in members if ":" not in m['title']]
            
            if not titles:
                return []
                
            # Step 2: Batch fetch Wikitext content
            # We batch in groups of 50 to respect API limits
            batch_size = 50
            for i in range(0, len(titles), batch_size):
                batch_titles = titles[i:i+batch_size]
                titles_param = urllib.parse.quote("|".join(batch_titles))
                content_url = f"https://en.wiktionary.org/w/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&titles={titles_param}&format=json"
                
                req2 = urllib.request.Request(content_url, headers={'User-Agent': 'OpenWorldDialects/1.0'})
                with urllib.request.urlopen(req2, context=ctx) as response2:
                    data2 = json.loads(response2.read().decode('utf-8'))
                    
                    pages = data2.get("query", {}).get("pages", {})
                    for page_id, page_info in pages.items():
                        title = page_info.get("title", "")
                        revs = page_info.get("revisions", [])
                        if not revs:
                            continue
                        content = revs[0].get("*", "")
                        
                        # Extract POJ from zh-pron templates (e.g., |mn=chia̍h or |mn=qz,xm,zz:chi̍t)
                        poj_match = re.search(r'\|(?:mn|poj)=([^\|\n\}]+)', content)
                        
                        # Extract gloss from the Verb section
                        verb_idx = content.find('===Verb===')
                        if verb_idx == -1: continue
                        
                        gloss_match = re.search(r'# (.*?)\n', content[verb_idx:])
                        
                        if poj_match and gloss_match:
                            raw_poj = poj_match.group(1).split(',')[0].split(':')[-1].split('/')[0].strip()
                            raw_gloss = gloss_match.group(1).strip()
                            
                            # Clean up wikilinks [[Link|Text]] -> Text
                            raw_gloss = re.sub(r'\[\[(?:[^\]]*\|)?([^\]]+)\]\]', r'\1', raw_gloss)
                            # Remove templates {{...}}
                            raw_gloss = re.sub(r'\{\{.*?\}\}', '', raw_gloss).strip()
                            
                            if raw_gloss.lower().startswith('to ') and len(raw_poj) > 1:
                                scraped_verbs.append({
                                    "hanzi": title,
                                    "poj": raw_poj,
                                    "english": raw_gloss
                                })
        except Exception as e:
            print(f"Deep API scrape encountered an error (ignoring and falling back to base): {e}")
            
        print(f"Deep scraping successfully parsed {len(scraped_verbs)} live Hokkien verbs.")
        return scraped_verbs

    def generate_full_paradigm(self, item):
        poj = item["poj"]
        
        # Hokkien heavily utilizes aspect particles rather than stem morphology.
        templates = {
            "taiwanese": {
                "pronouns": {"1s": "góa", "2s": "lí", "3s": "i", "1p": "gún", "2p": "lín", "3p": "in"},
                "past": {"aff": "{p} ū {v}", "neg": "{p} bô {v}"},
                "present": {"aff": "{p} {v}", "neg": "{p} m̄ {v}"},
                "future": {"aff": "{p} ē {v}", "neg": "{p} bē {v}"},
                "progressive": {"aff": "{p} teh {v}", "neg": "{p} bô teh {v}"},
                "imperative": {"aff": "chhiáⁿ {v}", "neg": "mài {v}"}
            },
            "amoy": {
                "pronouns": {"1s": "góa", "2s": "lí", "3s": "i", "1p": "gún", "2p": "lín", "3p": "in"},
                "past": {"aff": "{p} ū {v}", "neg": "{p} bô {v}"},
                "present": {"aff": "{p} {v}", "neg": "{p} m̄ {v}"},
                "future": {"aff": "{p} ē {v}", "neg": "{p} bōe {v}"},
                "progressive": {"aff": "{p} leh {v}", "neg": "{p} bô leh {v}"},
                "imperative": {"aff": "chhiáⁿ {v}", "neg": "mài {v}"}
            },
            "penang": {
                # Penang Hokkien has strong substratum influence affecting pronouns and aspect markers
                "pronouns": {"1s": "uá", "2s": "lú", "3s": "i", "1p": "uá-lâng", "2p": "lú-lâng", "3p": "i-lâng"},
                "past": {"aff": "{p} ū {v}", "neg": "{p} bô {v}"},
                "present": {"aff": "{p} {v}", "neg": "{p} m̄ {v}"},
                "future": {"aff": "{p} ē {v}", "neg": "{p} buē {v}"},
                "progressive": {"aff": "{p} tng-teh {v}", "neg": "{p} bô tng-teh {v}"},
                "imperative": {"aff": "chhiáⁿ {v}", "neg": "mài {v}"}
            }
        }

        dialect_conjugations = {}
        for code, gram in templates.items():
            aspects_data = {}
            for aspect in ["past", "present", "future", "progressive"]:
                aff_dict, neg_dict = {} , {}
                for p_data in self.persons:
                    pid = p_data["id"]
                    p = gram["pronouns"][pid]
                    aff_dict[pid] = gram[aspect]["aff"].format(p=p, v=poj)
                    neg_dict[pid] = gram[aspect]["neg"].format(p=p, v=poj)
                aspects_data[aspect] = {"affirmative": aff_dict, "negative": neg_dict}
            
            imp_aff, imp_neg = {}, {}
            for p_data in self.imperative_persons:
                pid = p_data["id"]
                imp_aff[pid] = gram["imperative"]["aff"].format(v=poj)
                imp_neg[pid] = gram["imperative"]["neg"].format(v=poj)
            aspects_data["imperative"] = {"affirmative": imp_aff, "negative": imp_neg}
            
            dialect_conjugations[code] = aspects_data
            
        return dialect_conjugations

    def generate_nominals(self, item):
        poj = item["poj"]
        return {
            "infinitive": {
                "affirmative": {"phrase": poj},
                "negative": {"phrase": f"mài {poj}"}
            },
            "doer_masculine_sg": {
                "affirmative": {"phrase": f"{poj} ê lâng"},
                "negative": {"phrase": f"bô {poj} ê lâng"}
            },
            "noun_of_place": {
                "affirmative": {"phrase": f"{poj} ê só͘-chāi"},
                "negative": {"phrase": f"bô {poj} ê só͘-chāi"}
            },
            "passive_participle": {
                "affirmative": {"phrase": f"hō͘ lâng {poj}"},
                "negative": {"phrase": f"bô hō͘ lâng {poj}"}
            }
        }

    def build_database(self):
        # 1. Start with rock-solid manual curations
        dataset = CORE_HOKKIEN_VERBS.copy()

        # 2. Augment with Deep Wiktionary Scrape
        scraped = self.deep_scrape_wiktionary()
        seen = {v["poj"] for v in dataset}
        for sv in scraped:
            if sv["poj"] not in seen:
                dataset.append(sv)
                seen.add(sv["poj"])
        
        db_path = "hokkien.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")
        # We use base_root to fit perfectly into the viewer's schema matching
        cursor.execute("CREATE TABLE IF NOT EXISTS roots (id INTEGER PRIMARY KEY AUTOINCREMENT, base_root TEXT UNIQUE, meaning_english TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS nominals (id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, category TEXT, polarity TEXT, phrase TEXT, FOREIGN KEY(root_id) REFERENCES roots(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS conjugations (id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, dialect TEXT, aspect TEXT, polarity TEXT, person_id TEXT, person TEXT, number TEXT, phrase TEXT, FOREIGN KEY(root_id) REFERENCES roots(id))")

        cursor.execute("DELETE FROM conjugations")
        cursor.execute("DELETE FROM nominals")
        cursor.execute("DELETE FROM roots")

        for item in dataset:
            # We combine the Hanzi and English meaning so both display in the UI cleanly
            formatted_meaning = f"[{item['hanzi']}] {item['english']}"
            
            try:
                cursor.execute("INSERT INTO roots (base_root, meaning_english) VALUES (?, ?)", (item["poj"], formatted_meaning))
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
        print(f"Hokkien (Min Nan) SQLite Dataset generated successfully: '{db_path}'")

if __name__ == "__main__":
    pipeline = HokkienPipeline()
    pipeline.build_database()