import json
import ssl
import sqlite3
import urllib.request
import os

# Ultra-common irregular verbs explicitly overridden to preserve absolute accuracy 
# within an otherwise systematically rule-generated pipeline.
IRREGULAR_OVERRIDES = {
    "ser": {
        "present": {"1s":"soy", "2s":"eres", "3s":"es", "1p":"somos", "2p":"sois", "3p":"son", "2s_rio":"sos", "2s_chi":"soi"},
        "past": {"1s":"fui", "2s":"fuiste", "3s":"fue", "1p":"fuimos", "2p":"fuisteis", "3p":"fueron"},
        "imperfect": {"1s":"era", "2s":"eras", "3s":"era", "1p":"éramos", "2p":"erais", "3p":"eran"},
        "future": {"1s":"seré", "2s":"serás", "3s":"será", "1p":"seremos", "2p":"seréis", "3p":"serán"},
        "subj_present": {"1s":"sea", "2s":"seas", "3s":"sea", "1p":"seamos", "2p":"seáis", "3p":"sean", "2s_rio":"seas", "2s_chi":"seáis"},
        "imperative_aff": {"2s":"sé", "2p":"sed", "2s_rio":"sé"},
        "gerund": "siendo", "participle": "sido"
    },
    "ir": {
        "present": {"1s":"voy", "2s":"vas", "3s":"va", "1p":"vamos", "2p":"vais", "3p":"van", "2s_rio":"vas", "2s_chi":"vai"},
        "past": {"1s":"fui", "2s":"fuiste", "3s":"fue", "1p":"fuimos", "2p":"fuisteis", "3p":"fueron"},
        "imperfect": {"1s":"iba", "2s":"ibas", "3s":"iba", "1p":"íbamos", "2p":"ibais", "3p":"iban"},
        "future": {"1s":"iré", "2s":"irás", "3s":"irá", "1p":"iremos", "2p":"iréis", "3p":"irán"},
        "subj_present": {"1s":"vaya", "2s":"vayas", "3s":"vaya", "1p":"vayamos", "2p":"vayáis", "3p":"vayan", "2s_rio":"vayas", "2s_chi":"vayáis"},
        "imperative_aff": {"2s":"ve", "2p":"id", "2s_rio":"andá"},
        "gerund": "yendo", "participle": "ido"
    },
    "estar": {
        "present": {"1s":"estoy", "2s":"estás", "3s":"está", "1p":"estamos", "2p":"estáis", "3p":"están", "2s_rio":"estás", "2s_chi":"estái"},
        "past": {"1s":"estuve", "2s":"estuviste", "3s":"estuvo", "1p":"estuvimos", "2p":"estuvisteis", "3p":"estuvieron"},
        "imperfect": {"1s":"estaba", "2s":"estabas", "3s":"estaba", "1p":"estábamos", "2p":"estabais", "3p":"estaban"},
        "future": {"1s":"estaré", "2s":"estarás", "3s":"estará", "1p":"estaremos", "2p":"estaréis", "3p":"estarán"},
        "subj_present": {"1s":"esté", "2s":"estés", "3s":"esté", "1p":"estemos", "2p":"estéis", "3p":"estén", "2s_rio":"estés", "2s_chi":"estéis"},
        "imperative_aff": {"2s":"está", "2p":"estad", "2s_rio":"está"},
        "gerund": "estando", "participle": "estado"
    },
    "tener": {
        "present": {"1s":"tengo", "2s":"tienes", "3s":"tiene", "1p":"tenemos", "2p":"tenéis", "3p":"tienen", "2s_rio":"tenés", "2s_chi":"tení"},
        "past": {"1s":"tuve", "2s":"tuviste", "3s":"tuvo", "1p":"tuvimos", "2p":"tuvisteis", "3p":"tuvieron"},
        "imperfect": {"1s":"tenía", "2s":"tenías", "3s":"tenía", "1p":"teníamos", "2p":"teníais", "3p":"tenían"},
        "future": {"1s":"tendré", "2s":"tendrás", "3s":"tendrá", "1p":"tendremos", "2p":"tendréis", "3p":"tendrán"},
        "subj_present": {"1s":"tenga", "2s":"tengas", "3s":"tenga", "1p":"tengamos", "2p":"tengáis", "3p":"tengan", "2s_rio":"tengas", "2s_chi":"tengáis"},
        "imperative_aff": {"2s":"ten", "2p":"tened", "2s_rio":"tené"},
        "gerund": "teniendo", "participle": "tenido"
    },
    "hacer": {
        "present": {"1s":"hago", "2s":"haces", "3s":"hace", "1p":"hacemos", "2p":"hacéis", "3p":"hacen", "2s_rio":"hacés", "2s_chi":"hací"},
        "past": {"1s":"hice", "2s":"hiciste", "3s":"hizo", "1p":"hicimos", "2p":"hicisteis", "3p":"hicieron"},
        "imperfect": {"1s":"hacía", "2s":"hacías", "3s":"hacía", "1p":"hacíamos", "2p":"hacíais", "3p":"hacían"},
        "future": {"1s":"haré", "2s":"harás", "3s":"hará", "1p":"haremos", "2p":"haréis", "3p":"harán"},
        "subj_present": {"1s":"haga", "2s":"hagas", "3s":"haga", "1p":"hagamos", "2p":"hagáis", "3p":"hagan", "2s_rio":"hagas", "2s_chi":"hagáis"},
        "imperative_aff": {"2s":"haz", "2p":"haced", "2s_rio":"hacé"},
        "gerund": "haciendo", "participle": "hecho"
    },
    "dar": {
        "present": {"1s":"doy", "2s":"das", "3s":"da", "1p":"damos", "2p":"dais", "3p":"dan", "2s_rio":"das", "2s_chi":"dai"},
        "past": {"1s":"di", "2s":"diste", "3s":"dio", "1p":"dimos", "2p":"disteis", "3p":"dieron"},
        "imperfect": {"1s":"daba", "2s":"dabas", "3s":"daba", "1p":"dábamos", "2p":"dabais", "3p":"daban"},
        "future": {"1s":"daré", "2s":"darás", "3s":"dará", "1p":"daremos", "2p":"daréis", "3p":"darán"},
        "subj_present": {"1s":"dé", "2s":"des", "3s":"dé", "1p":"demos", "2p":"deis", "3p":"den", "2s_rio":"des", "2s_chi":"deis"},
        "imperative_aff": {"2s":"da", "2p":"dad", "2s_rio":"da"},
        "gerund": "dando", "participle": "dado"
    },
    "ver": {
        "present": {"1s":"veo", "2s":"ves", "3s":"ve", "1p":"vemos", "2p":"veis", "3p":"ven", "2s_rio":"ves", "2s_chi":"vei"},
        "past": {"1s":"vi", "2s":"viste", "3s":"vio", "1p":"vimos", "2p":"visteis", "3p":"vieron"},
        "imperfect": {"1s":"veía", "2s":"veías", "3s":"veía", "1p":"veíamos", "2p":"veíais", "3p":"veían"},
        "future": {"1s":"veré", "2s":"verás", "3s":"verá", "1p":"veremos", "2p":"veréis", "3p":"verán"},
        "subj_present": {"1s":"vea", "2s":"veas", "3s":"vea", "1p":"veamos", "2p":"veáis", "3p":"vean", "2s_rio":"veas", "2s_chi":"veáis"},
        "imperative_aff": {"2s":"ve", "2p":"ved", "2s_rio":"ve"},
        "gerund": "viendo", "participle": "visto"
    },
    "decir": {
        "present": {"1s":"digo", "2s":"dices", "3s":"dice", "1p":"decimos", "2p":"decís", "3p":"dicen", "2s_rio":"decís", "2s_chi":"decís"},
        "past": {"1s":"dije", "2s":"dijiste", "3s":"dijo", "1p":"dijimos", "2p":"dijisteis", "3p":"dijeron"},
        "imperfect": {"1s":"decía", "2s":"decías", "3s":"decía", "1p":"decíamos", "2p":"decíais", "3p":"decían"},
        "future": {"1s":"diré", "2s":"dirás", "3s":"dirá", "1p":"diremos", "2p":"diréis", "3p":"dirán"},
        "subj_present": {"1s":"diga", "2s":"digas", "3s":"diga", "1p":"digamos", "2p":"digáis", "3p":"digan", "2s_rio":"digas", "2s_chi":"digáis"},
        "imperative_aff": {"2s":"di", "2p":"decid", "2s_rio":"decí"},
        "gerund": "diciendo", "participle": "dicho"
    },
    "oír": {
        "present": {"1s":"oigo", "2s":"oyes", "3s":"oye", "1p":"oímos", "2p":"oís", "3p":"oyen", "2s_rio":"oís", "2s_chi":"oís"},
        "past": {"1s":"oí", "2s":"oíste", "3s":"oyó", "1p":"oímos", "2p":"oísteis", "3p":"oyeron"},
        "imperfect": {"1s":"oía", "2s":"oías", "3s":"oía", "1p":"oíamos", "2p":"oíais", "3p":"oían"},
        "future": {"1s":"oiré", "2s":"oirás", "3s":"oirá", "1p":"oiremos", "2p":"oiréis", "3p":"oirán"},
        "subj_present": {"1s":"oiga", "2s":"oigas", "3s":"oiga", "1p":"oigamos", "2p":"oigáis", "3p":"oigan", "2s_rio":"oigas", "2s_chi":"oigáis"},
        "imperative_aff": {"2s":"oye", "2p":"oíd", "2s_rio":"oí"},
        "gerund": "oyendo", "participle": "oído"
    },
    "reír": {
        "present": {"1s":"río", "2s":"ríes", "3s":"ríe", "1p":"reímos", "2p":"reís", "3p":"ríen", "2s_rio":"reís", "2s_chi":"reís"},
        "past": {"1s":"reí", "2s":"reíste", "3s":"rio", "1p":"reímos", "2p":"reísteis", "3p":"rieron"},
        "imperfect": {"1s":"reía", "2s":"reías", "3s":"reía", "1p":"reíamos", "2p":"reíais", "3p":"reían"},
        "future": {"1s":"reiré", "2s":"reirás", "3s":"reirá", "1p":"reiremos", "2p":"reiréis", "3p":"reirán"},
        "subj_present": {"1s":"ría", "2s":"rías", "3s":"ría", "1p":"riamos", "2p":"riáis", "3p":"rían", "2s_rio":"rías", "2s_chi":"riáis"},
        "imperative_aff": {"2s":"ríe", "2p":"reíd", "2s_rio":"reí"},
        "gerund": "riendo", "participle": "reído"
    }
}

class SpanishPhonologyEngine:
    @staticmethod
    def is_valid_infinitive(word: str) -> bool:
        w = word[:-2] if word.endswith('se') else word
        if w in ['ir', 'ver', 'dar', 'ser', 'oír', 'reír']:
            return True
        return w.endswith(('ar', 'er', 'ir', 'ír')) and len(w) >= 3

    @staticmethod
    def get_stem_and_class(infinitive: str):
        w = infinitive[:-2] if infinitive.endswith('se') else infinitive
        if w == 'ir': return '', 'ir'
        if len(w) < 3: return None, None
        
        # Normalize class to prevent crash on accented endings (e.g. oír -> ír -> ir)
        vclass = 'ir' if w.endswith('ír') else w[-2:]
        return w[:-2], vclass

    @staticmethod
    def get_gerund(stem: str, vclass: str):
        if vclass == 'ar': return stem + "ando"
        if stem.endswith(('a','e','o')) and vclass in ['er', 'ir']:
            return stem + "yendo"
        return stem + "iendo"

    @staticmethod
    def get_participle(stem: str, vclass: str):
        if vclass == 'ar': return stem + "ado"
        if stem.endswith(('a','e','o')) and vclass in ['er', 'ir']:
            return stem + "ído"
        return stem + "ido"

    @staticmethod
    def generate_forms(stem: str, vclass: str, infinitive: str):
        if infinitive in IRREGULAR_OVERRIDES:
            return dict(IRREGULAR_OVERRIDES[infinitive])

        f = { 'present': {}, 'past': {}, 'imperfect': {}, 'future': {}, 'subj_present': {}, 'imperative_aff': {} }
        
        if vclass == 'ar':
            f['present'] = {'1s':'o', '2s':'as', '3s':'a', '1p':'amos', '2p':'áis', '3p':'an', '2s_rio':'ás', '2s_chi':'ái'}
            f['past'] = {'1s':'é', '2s':'aste', '3s':'ó', '1p':'amos', '2p':'asteis', '3p':'aron'}
            f['imperfect'] = {'1s':'aba', '2s':'abas', '3s':'aba', '1p':'ábamos', '2p':'abais', '3p':'aban'}
            f['subj_present'] = {'1s':'e', '2s':'es', '3s':'e', '1p':'emos', '2p':'éis', '3p':'en', '2s_rio':'es', '2s_chi':'ís'}
            f['imperative_aff'] = {'2s':'a', '2p':'ad', '2s_rio':'á'}
        elif vclass == 'er':
            f['present'] = {'1s':'o', '2s':'es', '3s':'e', '1p':'emos', '2p':'éis', '3p':'en', '2s_rio':'és', '2s_chi':'í'}
            f['past'] = {'1s':'í', '2s':'iste', '3s':'ió', '1p':'imos', '2p':'isteis', '3p':'ieron'}
            f['imperfect'] = {'1s':'ía', '2s':'ías', '3s':'ía', '1p':'íamos', '2p':'íais', '3p':'ían'}
            f['subj_present'] = {'1s':'a', '2s':'as', '3s':'a', '1p':'amos', '2p':'áis', '3p':'an', '2s_rio':'as', '2s_chi':'áis'}
            f['imperative_aff'] = {'2s':'e', '2p':'ed', '2s_rio':'é'}
        elif vclass == 'ir':
            f['present'] = {'1s':'o', '2s':'es', '3s':'e', '1p':'imos', '2p':'ís', '3p':'en', '2s_rio':'ís', '2s_chi':'ís'}
            f['past'] = {'1s':'í', '2s':'iste', '3s':'ió', '1p':'imos', '2p':'isteis', '3p':'ieron'}
            f['imperfect'] = {'1s':'ía', '2s':'ías', '3s':'ía', '1p':'íamos', '2p':'íais', '3p':'ían'}
            f['subj_present'] = {'1s':'a', '2s':'as', '3s':'a', '1p':'amos', '2p':'áis', '3p':'an', '2s_rio':'as', '2s_chi':'áis'}
            f['imperative_aff'] = {'2s':'e', '2p':'id', '2s_rio':'í'}

        f['future'] = {p: infinitive + suf for p, suf in zip(['1s','2s','3s','1p','2p','3p'], ['é','ás','á','emos','éis','án'])}

        for tense in ['present', 'past', 'imperfect', 'subj_present', 'imperative_aff']:
            for p, suf in f[tense].items():
                f[tense][p] = stem + suf

        # Orthographic morphological adjustments automatically handled for regular verbs
        if vclass == 'ar':
            def adjust_ar(w):
                return w.replace('cé', 'qué').replace('gé', 'gué').replace('zé', 'cé').replace('ce', 'que').replace('ge', 'gue').replace('ze', 'ce')
            f['past']['1s'] = adjust_ar(f['past']['1s'])
            for p in f['subj_present']:
                f['subj_present'][p] = adjust_ar(f['subj_present'][p])
        elif vclass in ['er', 'ir']:
            def adj_er_ir(w):
                if w.endswith('co'): return w[:-2] + 'zo'
                if w.endswith('go') and infinitive.endswith('ger'): return w[:-2] + 'jo'
                if w.endswith('go') and infinitive.endswith('gir'): return w[:-2] + 'jo'
                if w.endswith('ca'): return w[:-2] + 'za'
                if w.endswith('ga') and infinitive.endswith('ger'): return w[:-2] + 'ja'
                if w.endswith('ga') and infinitive.endswith('gir'): return w[:-2] + 'ja'
                return w
            f['present']['1s'] = adj_er_ir(f['present']['1s'])
            for p in f['subj_present']:
                f['subj_present'][p] = adj_er_ir(f['subj_present'][p])
                
        f['gerund'] = SpanishPhonologyEngine.get_gerund(stem, vclass)
        f['participle'] = SpanishPhonologyEngine.get_participle(stem, vclass)
        return f

DIALECTS = {
    "peninsular": {"1s": "yo", "2s": "tú", "3s": "él/ella", "1p": "nosotros", "2p": "vosotros", "3p": "ellos/ellas"},
    "latam": {"1s": "yo", "2s": "tú", "3s": "él/ella", "1p": "nosotros", "2p": "ustedes", "3p": "ellos/ellas"},
    "rioplatense": {"1s": "yo", "2s": "vos", "3s": "él/ella", "1p": "nosotros", "2p": "ustedes", "3p": "ellos/ellas"},
    "chilean": {"1s": "yo", "2s": "tú", "3s": "él/ella", "1p": "nosotros", "2p": "ustedes", "3p": "ellos/ellas"},
}

class SpanishPipeline:
    def __init__(self):
        self.dialects = [
            {"code": "peninsular", "name": "Peninsular (Spain)"},
            {"code": "latam", "name": "Latin American"},
            {"code": "rioplatense", "name": "Rioplatense (Argentina/Uruguay)"},
            {"code": "chilean", "name": "Chilean (Informal)"}
        ]

        self.persons = [
            {"id": "1s", "p": "1", "n": "sg", "g": "c"},
            {"id": "2s", "p": "2", "n": "sg", "g": "c"},
            {"id": "3s", "p": "3", "n": "sg", "g": "c"},
            {"id": "1p", "p": "1", "n": "pl", "g": "c"},
            {"id": "2p", "p": "2", "n": "pl", "g": "c"},
            {"id": "3p", "p": "3", "n": "pl", "g": "c"}
        ]
        
        self.imperative_persons = [
            {"id": "2s", "p": "2", "n": "sg", "g": "c"},
            {"id": "2p", "p": "2", "n": "pl", "g": "c"}
        ]

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

        dict_url = "https://dl.fbaipublicfiles.com/arrival/dictionaries/en-es.txt"
        print(f"Fetching live dictionary from FB MUSE: {dict_url} ...")
        req_dict = urllib.request.Request(dict_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_dict, context=ctx) as response:
            data = response.read().decode("utf-8").strip().split("\n")

        print("Intersecting datasets and extracting Spanish verbs...")
        spanish_dict = {}
        for line in data:
            parts = line.strip().split()
            if len(parts) == 2:
                en_w, es_w = parts[0].lower(), parts[1].lower()
                if en_w in valid_english_verbs and es_w != en_w:
                    if SpanishPhonologyEngine.is_valid_infinitive(es_w):
                        base_es = es_w[:-2] if es_w.endswith('se') else es_w
                        if not base_es.isalpha() and 'í' not in base_es: # ensure valid spanish charset
                            continue
                            
                        if base_es not in spanish_dict:
                            spanish_dict[base_es] = []
                        if en_w not in spanish_dict[base_es]:
                            spanish_dict[base_es].append(en_w)

        roots_data = []
        for es_word in sorted(spanish_dict.keys()):
            en_meanings = spanish_dict[es_word]
            meaning_str = "to " + ", ".join(en_meanings[:3])
            roots_data.append({"root": es_word, "meaning_en": meaning_str})

        print(f"Successfully filtered {len(roots_data)} Spanish verb roots.")
        return roots_data

    def generate_full_paradigm(self, infinitive: str):
        stem, vclass = SpanishPhonologyEngine.get_stem_and_class(infinitive)
        if not vclass: return {}

        forms = SpanishPhonologyEngine.generate_forms(stem, vclass, infinitive)
        gerund = forms['gerund']

        dialect_conjugations = {}
        for d_code, pronouns in DIALECTS.items():
            aspects = {
                "past": {"affirmative": {}, "negative": {}},
                "present": {"affirmative": {}, "negative": {}},
                "imperfect": {"affirmative": {}, "negative": {}},
                "future": {"affirmative": {}, "negative": {}},
                "progressive": {"affirmative": {}, "negative": {}},
                "imperative": {"affirmative": {}, "negative": {}}
            }
            
            person_map = {"1s": "1s", "3s": "3s", "1p": "1p", "3p": "3p"}
            if d_code == "peninsular":
                person_map["2s"] = "2s"
                person_map["2p"] = "2p"
            elif d_code == "latam":
                person_map["2s"] = "2s"
                person_map["2p"] = "3p"
            elif d_code == "rioplatense":
                person_map["2s"] = "2s_rio"
                person_map["2p"] = "3p"
            elif d_code == "chilean":
                person_map["2s"] = "2s_chi"
                person_map["2p"] = "3p"

            for p_id in ["1s", "2s", "3s", "1p", "2p", "3p"]:
                pro = pronouns[p_id]
                f_id = person_map[p_id]
                
                # Aspectual Matrix
                word_pres = forms['present'][f_id]
                aspects['present']['affirmative'][p_id] = f"{pro} {word_pres}"
                aspects['present']['negative'][p_id] = f"{pro} no {word_pres}"

                f_id_past = "3p" if p_id == "2p" and d_code != "peninsular" else ("2s" if p_id == "2s" else f_id)
                word_past = forms['past'][f_id_past]
                aspects['past']['affirmative'][p_id] = f"{pro} {word_past}"
                aspects['past']['negative'][p_id] = f"{pro} no {word_past}"

                word_imp = forms['imperfect'][f_id_past]
                aspects['imperfect']['affirmative'][p_id] = f"{pro} {word_imp}"
                aspects['imperfect']['negative'][p_id] = f"{pro} no {word_imp}"

                f_id_fut = "3p" if p_id == "2p" and d_code != "peninsular" else ("2s" if p_id == "2s" else f_id)
                word_fut = forms['future'][f_id_fut]
                aspects['future']['affirmative'][p_id] = f"{pro} {word_fut}"
                aspects['future']['negative'][p_id] = f"{pro} no {word_fut}"

                estar_f_id = "3p" if p_id == "2p" and d_code != "peninsular" else (
                    "2s_rio" if p_id == "2s" and d_code == "rioplatense" else (
                    "2s_chi" if p_id == "2s" and d_code == "chilean" else (
                    "2s" if p_id == "2s" else f_id)))
                estar_form = IRREGULAR_OVERRIDES["estar"]["present"][estar_f_id]
                aspects['progressive']['affirmative'][p_id] = f"{pro} {estar_form} {gerund}"
                aspects['progressive']['negative'][p_id] = f"{pro} no {estar_form} {gerund}"

            # Imperative
            for p_id in ["2s", "2p"]:
                pro = pronouns[p_id]
                
                if p_id == "2s":
                    word_aff = forms['imperative_aff']['2s_rio'] if d_code == "rioplatense" else forms['imperative_aff']['2s']
                    word_neg = "no " + forms['subj_present']['2s_chi'] if d_code == "chilean" else (
                               "no " + forms['subj_present']['2s_rio'] if d_code == "rioplatense" else 
                               "no " + forms['subj_present']['2s'])
                else:
                    word_aff = forms['imperative_aff']['2p'] if d_code == "peninsular" else forms['subj_present']['3p']
                    word_neg = "no " + forms['subj_present']['2p'] if d_code == "peninsular" else "no " + forms['subj_present']['3p']

                aspects['imperative']['affirmative'][p_id] = f"¡{word_aff}!"
                aspects['imperative']['negative'][p_id] = f"¡{word_neg}!"
                
            dialect_conjugations[d_code] = aspects
        return dialect_conjugations

    def generate_nominals(self, infinitive: str):
        stem, vclass = SpanishPhonologyEngine.get_stem_and_class(infinitive)
        forms = SpanishPhonologyEngine.generate_forms(stem, vclass, infinitive)
        return {
            "infinitive": {
                "affirmative": {"phrase": infinitive},
                "negative": {"phrase": f"no {infinitive}"}
            },
            "masdar": {
                "affirmative": {"phrase": forms['gerund']},
                "negative": {"phrase": f"no {forms['gerund']}"}
            },
            "passive_participle": {
                "affirmative": {"phrase": forms['participle']},
                "negative": {"phrase": f"no {forms['participle']}"}
            }
        }

    def build_database(self):
        dataset = self.fetch_open_source_dataset()
        db_path = "spanish.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("CREATE TABLE IF NOT EXISTS roots (id INTEGER PRIMARY KEY AUTOINCREMENT, base_root TEXT UNIQUE, meaning_english TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS nominals (id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, category TEXT, polarity TEXT, phrase TEXT, FOREIGN KEY(root_id) REFERENCES roots(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS conjugations (id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, dialect TEXT, aspect TEXT, polarity TEXT, person_id TEXT, person TEXT, number TEXT, gender TEXT, phrase TEXT, FOREIGN KEY(root_id) REFERENCES roots(id))")

        cursor.execute("DELETE FROM conjugations")
        cursor.execute("DELETE FROM nominals")
        cursor.execute("DELETE FROM roots")

        for item in dataset:
            base_root = item.get("root", "")
            raw_english = item.get("meaning_en", "")

            try:
                cursor.execute("INSERT INTO roots (base_root, meaning_english) VALUES (?, ?)", (base_root, raw_english))
                root_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                continue

            nominals = self.generate_nominals(base_root)
            nom_tuples = []
            for n_type, polarities in nominals.items():
                for pol, scripts in polarities.items():
                    nom_tuples.append((root_id, n_type, pol, scripts["phrase"]))
            
            cursor.executemany("INSERT INTO nominals (root_id, category, polarity, phrase) VALUES (?, ?, ?, ?)", nom_tuples)

            dialectal_conjugations = self.generate_full_paradigm(base_root)
            conj_tuples = []

            for d in self.dialects:
                d_code = d["code"]
                d_conjugations = dialectal_conjugations.get(d_code, {})
                for aspect, pol_dict in d_conjugations.items():
                    for pol, persons_dict in pol_dict.items():
                        for pid, phrase in persons_dict.items():
                            p_info = next((x for x in self.persons if x["id"] == pid), None)
                            if not p_info:
                                p_info = next((x for x in self.imperative_persons if x["id"] == pid))

                            conj_tuples.append((
                                root_id, d_code, aspect, pol, pid,
                                p_info["p"], p_info["n"], p_info["g"], phrase
                            ))

            cursor.executemany("""
                INSERT INTO conjugations (root_id, dialect, aspect, polarity, person_id, person, number, gender, phrase) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, conj_tuples)

        conn.commit()
        conn.close()
        print(f"Spanish Verb Database Generated Successfully: '{db_path}'")

if __name__ == "__main__":
    pipeline = SpanishPipeline()
    pipeline.build_database()