import json
import math
import re
import ssl
import sqlite3
import urllib.error
import urllib.request
import xml.dom.minidom
import xml.etree.ElementTree as ET


class MITLicensedRootPipeline:
    def __init__(self):
        self.arabizi_map = {
            "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "7", "خ": "5",
            "د": "d", "ذ": "dh", "ر": "r", "ز": "z", "س": "s", "ش": "sh",
            "ص": "9", "ض": "9'", "ط": "6", "ظ": "6'", "ع": "3", "غ": "3'",
            "ف": "f", "ق": "8", "ك": "k", "ل": "l", "م": "m", "ن": "n",
            "ه": "h", "و": "w", "ي": "y",
            "ء": "2", "أ": "2", "إ": "2", "آ": "2", "ؤ": "2", "ئ": "2",
            "ا": "a", "ى": "y", "ة": "t", "ـ": "",
        }

        self.lexical_backup = {
            "خرب": "to be or become ruined, desolate, or destroyed; to lay waste, demolish",
            "صبغ": "to dye, color, or tint; to immerse or dip (such as hands or food)",
            "جنف": "to incline, decline, deviate, or act unjustly; to swerve from truth",
            "كتب": "to write, record, prescribe, or decree",
            "سفك": "to shed or pour forth (blood or tears)",
            "علم": "to know, comprehend, perceive, or have knowledge",
        }

        self.dialects = [
            {"code": "msa", "name": "Modern Standard Arabic", "region": "Pan-Arab / Classical"},
            {"code": "egyptian", "name": "Egyptian Masri", "region": "Cairene / Nile Basin"},
            {"code": "levantine", "name": "Levantine Shami", "region": "Lebanese / Syrian"},
            {"code": "levantine_2_palestine", "name": "Palestinian / South Levantine", "region": "Jerusalem / Jordan"},
            {"code": "iraqi", "name": "Mesopotamian Iraqi", "region": "Baghdadi / Tigris-Euphrates"},
            {"code": "gulf", "name": "Khaliji Gulf", "region": "Eastern Arabian / UAE / Kuwait"},
            {"code": "najdi", "name": "Najdi Peninsular", "region": "Central Arabian Bedouin"},
            {"code": "hijazi", "name": "Hijazi Western", "region": "Mecca / Medina / Jeddah"},
            {"code": "yemeni", "name": "South Arabian Yemeni", "region": "San'ani / Southern Semitic"},
            {"code": "sudanese", "name": "Sudanese Nilotic", "region": "Khartoum / Gezira"},
            {"code": "darija", "name": "Moroccan Darija", "region": "Western Maghrebi"},
            {"code": "tunisian", "name": "Tunisian Tounsi", "region": "Eastern Maghrebi"},
        ]

        self.persons = [
            {"id": "1s", "p": "1", "n": "sg", "g": "c", "name": "I (First Person Singular)"},
            {"id": "2ms", "p": "2", "n": "sg", "g": "m", "name": "You (Second Person Masc Singular)"},
            {"id": "2fs", "p": "2", "n": "sg", "g": "f", "name": "You (Second Person Fem Singular)"},
            {"id": "3ms", "p": "3", "n": "sg", "g": "m", "name": "He (Third Person Masc Singular)"},
            {"id": "3fs", "p": "3", "n": "sg", "g": "f", "name": "She (Third Person Fem Singular)"},
            {"id": "1p", "p": "1", "n": "pl", "g": "c", "name": "We (First Person Plural)"},
            {"id": "2p", "p": "2", "n": "pl", "g": "c", "name": "You All (Second Person Plural)"},
            {"id": "3p", "p": "3", "n": "pl", "g": "c", "name": "They (Third Person Plural)"},
        ]

        self.imperative_persons = [
            {"id": "2ms", "p": "2", "n": "sg", "g": "m"},
            {"id": "2fs", "p": "2", "n": "sg", "g": "f"},
            {"id": "2p", "p": "2", "n": "pl", "g": "c"},
        ]

    def sanitize_arabic(self, arabic_text: str) -> str:
        if not arabic_text:
            return ""
        cleaned = re.sub(r"[\u064B-\u0652\u0640]", "", arabic_text)
        cleaned = re.sub(r"[^\u0621-\u064A\s]", "", cleaned)
        return cleaned.strip()

    def generate_arabizi(self, arabic_root: str) -> str:
        clean_root = self.sanitize_arabic(arabic_root)
        arabizi_chars = [
            self.arabizi_map.get(char, char)
            for char in clean_root
            if not char.isspace()
        ]
        return "-".join(arabizi_chars)

    def inflect_gerund(self, verb: str) -> str:
        verb = verb.lower().strip()
        if not verb or not verb.isalpha():
            return verb
        if verb.endswith("ie"):
            return verb[:-2] + "ying"
        if verb.endswith(("ye", "oe", "ee")):
            return verb + "ing"
        if verb.endswith("c"):
            return verb + "king"
        if verb.endswith("e") and len(verb) > 2 and verb[-2] not in "aeiou":
            return verb[:-1] + "ing"
        if len(verb) >= 3:
            c1, v, c2 = verb[-3], verb[-2], verb[-1]
            if (
                c1 in "bcdfghjklmnpqrstvwxyz"
                and v in "aeiou"
                and c2 in "bcdfghjklmnpqrstvz"
                and c2 not in "wxy"
                and len(verb) <= 5
            ):
                return verb + c2 + "ing"
        return verb + "ing"

    def format_english_definition(self, raw_text: str, mother_arabic: str) -> str:
        text = raw_text.strip()
        text_lower = text.lower()

        infinitive_match = re.match(r"^to\s+([a-z\s,\/\(\)]+?)(?:\.|$)", text_lower)
        if (
            infinitive_match
            and not text_lower.startswith("the root")
            and not text_lower.startswith("the word")
        ):
            verb_chain = infinitive_match.group(1).strip()
            tokens = re.split(r"(\b(?:or|and)\b|,|\/)", verb_chain)
            inflected_tokens = []
            for token in tokens:
                clean_t = token.strip()
                if clean_t in ["or", "and", ",", "/"] or not clean_t:
                    inflected_tokens.append(f" {clean_t} " if clean_t in ["or", "and"] else clean_t)
                else:
                    words = clean_t.split()
                    if words:
                        words[0] = self.inflect_gerund(words[0])
                        inflected_tokens.append(" ".join(words))

            result = "".join(inflected_tokens)
            result = re.sub(r"\s+", " ", result).strip()
            return f"Related to {result}."

        def replace_means_to(match):
            prefix, verb1, conj, verb2 = match.group(1), match.group(2), match.group(3), match.group(4)
            return f"{prefix} relates to {self.inflect_gerund(verb1)} {conj} {self.inflect_gerund(verb2)}"

        text = re.sub(r"\b(primarily\s+means)\s+to\s+([a-z]+)\s+(or|and)\s+([a-z]+)\b", replace_means_to, text, flags=re.IGNORECASE)

        def replace_single_to(match):
            return f"{match.group(1)} relates to {self.inflect_gerund(match.group(2))}"

        text = re.sub(r"\b(primarily\s+means)\s+to\s+([a-z]+)\b", replace_single_to, text, flags=re.IGNORECASE)
        text = re.sub(r"\brefers\s+related\s+with\b", "refers to", text, flags=re.IGNORECASE)
        text = re.sub(r"\bprimarily\s+means\s+related\s+with\b", "primarily relates to", text, flags=re.IGNORECASE)
        text = re.sub(r"\brelated\s+with\b", "related to", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        if text and not text.endswith((".", '"', "'")):
            text += "."
        return text

    def validate_semantic_alignment(self, mother_arabic: str, text_en: str) -> bool:
        if not text_en or not mother_arabic:
            return False
        arabic_tokens = re.findall(r"[\u0621-\u064A]+", text_en[:80])
        if arabic_tokens:
            cited_arabic = self.sanitize_arabic(arabic_tokens[0])
            if len(cited_arabic) >= 3:
                root_set = set(mother_arabic)
                cited_set = set(cited_arabic)
                if len(root_set.intersection(cited_set)) < 2 or mother_arabic[0] not in cited_set:
                    return False
        text_lower = text_en.lower()
        if mother_arabic == "خرب" and any(w in text_lower for w in ["amber", "electricity", "kahrab", "electrostatic"]):
            return False
        return True

    def generate_full_paradigm(self, A1, A2, A3, E1, E2, E3):
        base_ar = f"{A1}{A2}{A3}"
        base_en = f"{E1}{E2}{E3}"

        past_affixes = {
            "1s":  {"ar_suf": "ت",  "en_suf": "t"},
            "2ms": {"ar_suf": "ت",  "en_suf": "ta"},
            "2fs": {"ar_suf": "ت",  "en_suf": "ti"},
            "3ms": {"ar_suf": "",   "en_suf": ""},
            "3fs": {"ar_suf": "ت",  "en_suf": "at"},
            "1p":  {"ar_suf": "نا", "en_suf": "na"},
            "2p":  {"ar_suf": "توا", "en_suf": "tu"},
            "3p":  {"ar_suf": "وا", "en_suf": "oo"},
        }

        pres_affixes = {
            "1s":  {"ar_pre": "أ", "ar_suf": "",   "en_pre": "a",  "en_suf": ""},
            "2ms": {"ar_pre": "ت", "ar_suf": "",   "en_pre": "te", "en_suf": ""},
            "2fs": {"ar_pre": "ت", "ar_suf": "ي",  "en_pre": "te", "en_suf": "i"},
            "3ms": {"ar_pre": "ي", "ar_suf": "",   "en_pre": "ye", "en_suf": ""},
            "3fs": {"ar_pre": "ت", "ar_suf": "",   "en_pre": "te", "en_suf": ""},
            "1p":  {"ar_pre": "ن", "ar_suf": "",   "en_pre": "ne", "en_suf": ""},
            "2p":  {"ar_pre": "ت", "ar_suf": "وا", "en_pre": "te", "en_suf": "oo"},
            "3p":  {"ar_pre": "ي", "ar_suf": "وا", "en_pre": "ye", "en_suf": "oo"},
        }

        dialect_specs = {
            "msa": {
                "pres_pfx_ar": "", "pres_pfx_en": "",
                "fut_pfx_ar": "سـ", "fut_pfx_en": "sa-",
                "prog_pfx_ar": "في طور الـ", "prog_pfx_en": "fi-tawr-",
                "past_neg_ar": ("ما ", ""), "past_neg_en": ("ma ", ""),
                "pres_neg_ar": ("لا ", ""), "pres_neg_en": ("la ", ""),
                "fut_neg_ar": ("لن ", ""), "fut_neg_en": ("lan ", ""),
                "prog_neg_ar": ("ليس في طور الـ", ""), "prog_neg_en": ("laysa fi-tawr-", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "e",
                "imp_neg_ar": ("لا تـ", ""), "imp_neg_en": ("la te-", "")
            },
            "egyptian": {
                "pres_pfx_ar": "بـ", "pres_pfx_en": "bi-",
                "fut_pfx_ar": "حـ", "fut_pfx_en": "7a-",
                "prog_pfx_ar": "عمال بـ", "prog_pfx_en": "3ammal bi-",
                "past_neg_ar": ("ما", "ش"), "past_neg_en": ("ma-", "-sh"),
                "pres_neg_ar": ("ما", "ش"), "pres_neg_en": ("ma-", "-sh"),
                "fut_neg_ar": ("مش حـ", ""), "fut_neg_en": ("mesh 7a-", ""),
                "prog_neg_ar": ("مش عمال بـ", ""), "prog_neg_en": ("mesh 3ammal bi-", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("ماتـ", "ش"), "imp_neg_en": ("mat-", "-sh")
            },
            "levantine": {
                "pres_pfx_ar": "بـ", "pres_pfx_en": "b-",
                "fut_pfx_ar": "رح ", "fut_pfx_en": "ra7 ",
                "prog_pfx_ar": "عم بـ", "prog_pfx_en": "3am b-",
                "past_neg_ar": ("ما ", ""), "past_neg_en": ("ma ", ""),
                "pres_neg_ar": ("ما بـ", ""), "pres_neg_en": ("ma b-", ""),
                "fut_neg_ar": ("ما رح ", ""), "fut_neg_en": ("ma ra7 ", ""),
                "prog_neg_ar": ("مش عم بـ", ""), "prog_neg_en": ("mish 3am b-", ""),
                "imp_pre_ar": "", "imp_pre_en": "",
                "imp_neg_ar": ("ما تـ", ""), "imp_neg_en": ("ma te-", "")
            },
            "levantine_2_palestine": {
                "pres_pfx_ar": "بـ", "pres_pfx_en": "b-",
                "fut_pfx_ar": "بدّو ", "fut_pfx_en": "biddo ",
                "prog_pfx_ar": "قاعد بـ", "prog_pfx_en": "gaa3ed b-",
                "past_neg_ar": ("ما ", "ش"), "past_neg_en": ("ma ", "-sh"),
                "pres_neg_ar": ("ما بـ", "ش"), "pres_neg_en": ("mab-", "-sh"),
                "fut_neg_ar": ("مش رح ", ""), "fut_neg_en": ("mish ra7 ", ""),
                "prog_neg_ar": ("مش قاعد بـ", ""), "prog_neg_en": ("mish gaa3ed b-", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("ما تـ", "ش"), "imp_neg_en": ("mate-", "-sh")
            },
            "iraqi": {
                "pres_pfx_ar": "دا", "pres_pfx_en": "da-",
                "fut_pfx_ar": "راح ", "fut_pfx_en": "ra7 ",
                "prog_pfx_ar": "كاعد دا", "prog_pfx_en": "ga3ed da-",
                "past_neg_ar": ("ما ", ""), "past_neg_en": ("ma ", ""),
                "pres_neg_ar": ("مادا", ""), "pres_neg_en": ("ma da-", ""),
                "fut_neg_ar": ("ما راح ", ""), "fut_neg_en": ("ma ra7 ", ""),
                "prog_neg_ar": ("مو كاعد دا", ""), "prog_neg_en": ("moo ga3ed da-", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("لا تـ", ""), "imp_neg_en": ("la te-", "")
            },
            "gulf": {
                "pres_pfx_ar": "", "pres_pfx_en": "",
                "fut_pfx_ar": "بيـ", "fut_pfx_en": "bi-",
                "prog_pfx_ar": "قاعد ", "prog_pfx_en": "gaa3ed ",
                "past_neg_ar": ("ما ", ""), "past_neg_en": ("ma ", ""),
                "pres_neg_ar": ("ما ", ""), "pres_neg_en": ("ma ", ""),
                "fut_neg_ar": ("ما راح ", ""), "fut_neg_en": ("ma ra7 ", ""),
                "prog_neg_ar": ("مو قاعد ", ""), "prog_neg_en": ("moo gaa3ed ", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("لا تـ", ""), "imp_neg_en": ("la ti-", "")
            },
            "najdi": {
                "pres_pfx_ar": "", "pres_pfx_en": "",
                "fut_pfx_ar": "بيـ", "fut_pfx_en": "bi-",
                "prog_pfx_ar": "جالس ", "prog_pfx_en": "jaalis ",
                "past_neg_ar": ("ما ", ""), "past_neg_en": ("ma ", ""),
                "pres_neg_ar": ("ما ", ""), "pres_neg_en": ("ma ", ""),
                "fut_neg_ar": ("ما هو بـ", ""), "fut_neg_en": ("mahoo bi-", ""),
                "prog_neg_ar": ("مهوب جالس ", ""), "prog_neg_en": ("mahoob jaalis ", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("لا تـ", ""), "imp_neg_en": ("la ti-", "")
            },
            "hijazi": {
                "pres_pfx_ar": "بيـ", "pres_pfx_en": "bi-",
                "fut_pfx_ar": "حيـ", "fut_pfx_en": "7a-",
                "prog_pfx_ar": "قاعد بيـ", "prog_pfx_en": "gaa3ed bi-",
                "past_neg_ar": ("ما ", ""), "past_neg_en": ("ma ", ""),
                "pres_neg_ar": ("ما بيـ", ""), "pres_neg_en": ("ma bi-", ""),
                "fut_neg_ar": ("ما حيـ", ""), "fut_neg_en": ("ma 7a-", ""),
                "prog_neg_ar": ("مو قاعد بيـ", ""), "prog_neg_en": ("moo gaa3ed bi-", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("لا تـ", ""), "imp_neg_en": ("la te-", "")
            },
            "yemeni": {
                "pres_pfx_ar": "بايـ", "pres_pfx_en": "ba-",
                "fut_pfx_ar": "عايـ", "fut_pfx_en": "3a-",
                "prog_pfx_ar": "عاد بيـ", "prog_pfx_en": "3ad bi-",
                "past_neg_ar": ("ما ", "ش"), "past_neg_en": ("ma ", "-sh"),
                "pres_neg_ar": ("ما بايـ", "ش"), "pres_neg_en": ("maba-", "-sh"),
                "fut_neg_ar": ("ما عايـ", "ش"), "fut_neg_en": ("ma 3a-", "-sh"),
                "prog_neg_ar": ("ما عاد بيـ", "ش"), "prog_neg_en": ("ma 3ad bi-", "-sh"),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("ما تـ", "ش"), "imp_neg_en": ("mate-", "-sh")
            },
            "sudanese": {
                "pres_pfx_ar": "بيـ", "pres_pfx_en": "bi-",
                "fut_pfx_ar": "حيـ", "fut_pfx_en": "7a-",
                "prog_pfx_ar": "قاعد بيـ", "prog_pfx_en": "gaa3ed bi-",
                "past_neg_ar": ("ما ", ""), "past_neg_en": ("ma ", ""),
                "pres_neg_ar": ("ما بيـ", ""), "pres_neg_en": ("ma bi-", ""),
                "fut_neg_ar": ("ما حيـ", ""), "fut_neg_en": ("ma 7a-", ""),
                "prog_neg_ar": ("ما قاعد بيـ", ""), "prog_neg_en": ("ma gaa3ed bi-", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("ما تـ", ""), "imp_neg_en": ("ma te-", "")
            },
            "darija": {
                "pres_pfx_ar": "كايـ", "pres_pfx_en": "kay-",
                "fut_pfx_ar": "غادي ", "fut_pfx_en": "ghadi ",
                "prog_pfx_ar": "كايـ", "prog_pfx_en": "kay-",
                "past_neg_ar": ("ما ", "ش"), "past_neg_en": ("ma ", "-sh"),
                "pres_neg_ar": ("ما كايـ", "ش"), "pres_neg_en": ("makay-", "-sh"),
                "fut_neg_ar": ("ما غاديش ", ""), "fut_neg_en": ("ma ghadish ", ""),
                "prog_neg_ar": ("ما كايـ", "ش"), "prog_neg_en": ("makay-", "-sh"),
                "imp_pre_ar": "", "imp_pre_en": "",
                "imp_neg_ar": ("ما تـ", "ش"), "imp_neg_en": ("mate-", "-sh")
            },
            "tunisian": {
                "pres_pfx_ar": "", "pres_pfx_en": "",
                "fut_pfx_ar": "باش ", "fut_pfx_en": "baash ",
                "prog_pfx_ar": "قاعد ", "prog_pfx_en": "gaa3ed ",
                "past_neg_ar": ("ما ", "ش"), "past_neg_en": ("ma ", "-sh"),
                "pres_neg_ar": ("ما ", "ش"), "pres_neg_en": ("ma ", "-sh"),
                "fut_neg_ar": ("مش باش ", ""), "fut_neg_en": ("mush baash ", ""),
                "prog_neg_ar": ("مش قاعد ", ""), "prog_neg_en": ("mush gaa3ed ", ""),
                "imp_pre_ar": "ا", "imp_pre_en": "i",
                "imp_neg_ar": ("ما تـ", "ش"), "imp_neg_en": ("mate-", "-sh")
            },
        }

        dialect_conjugations = {}

        for d in self.dialects:
            code = d["code"]
            spec = dialect_specs[code]
            aspects_data = {}

            past_aff = {}
            past_neg = {}
            for p in self.persons:
                pid = p["id"]
                aff = past_affixes[pid]
                stem_ar = f"{base_ar}{aff['ar_suf']}"
                stem_en = f"{E1}a{E2}a{E3}{aff['en_suf']}"
                past_aff[pid] = {"arabic": stem_ar, "arabizi": stem_en}

                pre_ar, suf_ar = spec["past_neg_ar"]
                pre_en, suf_en = spec["past_neg_en"]
                neg_ar = f"{pre_ar}{stem_ar}{suf_ar}"
                neg_en = f"{pre_en}{stem_en}{suf_en}".strip()
                past_neg[pid] = {"arabic": neg_ar, "arabizi": neg_en}
            aspects_data["past"] = {"affirmative": past_aff, "negative": past_neg}

            pres_aff = {}
            pres_neg = {}
            for p in self.persons:
                pid = p["id"]
                aff = pres_affixes[pid]
                stem_ar = f"{aff['ar_pre']}{base_ar}{aff['ar_suf']}"
                stem_en = f"{aff['en_pre']}{base_en}{aff['en_suf']}"

                pres_full_ar = f"{spec['pres_pfx_ar']}{stem_ar}"
                pres_full_en = f"{spec['pres_pfx_en']}{stem_en}"
                pres_aff[pid] = {"arabic": pres_full_ar, "arabizi": pres_full_en}

                pre_ar, suf_ar = spec["pres_neg_ar"]
                pre_en, suf_en = spec["pres_neg_en"]
                neg_ar = f"{pre_ar}{stem_ar}{suf_ar}"
                neg_en = f"{pre_en}{stem_en}{suf_en}".strip()
                pres_neg[pid] = {"arabic": neg_ar, "arabizi": neg_en}
            aspects_data["present"] = {"affirmative": pres_aff, "negative": pres_neg}

            fut_aff = {}
            fut_neg = {}
            for p in self.persons:
                pid = p["id"]
                aff = pres_affixes[pid]
                stem_ar = f"{aff['ar_pre']}{base_ar}{aff['ar_suf']}"
                stem_en = f"{aff['en_pre']}{base_en}{aff['en_suf']}"

                fut_ar = f"{spec['fut_pfx_ar']}{stem_ar}"
                fut_en = f"{spec['fut_pfx_en']}{stem_en}"
                fut_aff[pid] = {"arabic": fut_ar, "arabizi": fut_en}

                pre_ar, suf_ar = spec["fut_neg_ar"]
                pre_en, suf_en = spec["fut_neg_en"]
                neg_ar = f"{pre_ar}{stem_ar}{suf_ar}"
                neg_en = f"{pre_en}{stem_en}{suf_en}".strip()
                fut_neg[pid] = {"arabic": neg_ar, "arabizi": neg_en}
            aspects_data["future"] = {"affirmative": fut_aff, "negative": fut_neg}

            prog_aff = {}
            prog_neg = {}
            for p in self.persons:
                pid = p["id"]
                aff = pres_affixes[pid]
                stem_ar = f"{aff['ar_pre']}{base_ar}{aff['ar_suf']}"
                stem_en = f"{aff['en_pre']}{base_en}{aff['en_suf']}"

                p_ar = f"{spec['prog_pfx_ar']}{stem_ar}"
                p_en = f"{spec['prog_pfx_en']}{stem_en}"
                prog_aff[pid] = {"arabic": p_ar, "arabizi": p_en}

                pre_ar, suf_ar = spec["prog_neg_ar"]
                pre_en, suf_en = spec["prog_neg_en"]
                neg_ar = f"{pre_ar}{stem_ar}{suf_ar}"
                neg_en = f"{pre_en}{stem_en}{suf_en}".strip()
                prog_neg[pid] = {"arabic": neg_ar, "arabizi": neg_en}
            aspects_data["progressive"] = {"affirmative": prog_aff, "negative": prog_neg}

            imp_aff = {}
            imp_neg = {}
            imp_suffixes = {
                "2ms": {"ar": "", "en": ""},
                "2fs": {"ar": "ي", "en": "i"},
                "2p":  {"ar": "وا", "en": "oo"},
            }
            for ip in self.imperative_persons:
                pid = ip["id"]
                suf = imp_suffixes[pid]
                imp_ar = f"{spec['imp_pre_ar']}{base_ar}{suf['ar']}"
                imp_en = f"{spec['imp_pre_en']}{base_en}{suf['en']}"
                imp_aff[pid] = {"arabic": imp_ar, "arabizi": imp_en}

                pre_ar, suf_ar = spec["imp_neg_ar"]
                pre_en, suf_en = spec["imp_neg_en"]
                neg_ar = f"{pre_ar}{base_ar}{suf['ar']}{suf_ar}"
                neg_en = f"{pre_en}{base_en}{suf['en']}{suf_en}".strip()
                imp_neg[pid] = {"arabic": neg_ar, "arabizi": neg_en}
            aspects_data["imperative"] = {"affirmative": imp_aff, "negative": imp_neg}

            dialect_conjugations[code] = aspects_data

        return dialect_conjugations

    def generate_nominals(self, A1, A2, A3, E1, E2, E3):
        return {
            "active_participle": {
                "affirmative": {"arabic": f"{A1}ا{A2}{A3}", "arabizi": f"{E1}aa{E2}e{E3}"},
                "negative":    {"arabic": f"غير {A1}ا{A2}{A3}", "arabizi": f"gheir {E1}aa{E2}e{E3}"}
            },
            "passive_participle": {
                "affirmative": {"arabic": f"م{A1}{A2}و{A3}", "arabizi": f"ma{E1}{E2}oo{E3}"},
                "negative":    {"arabic": f"غير م{A1}{A2}و{A3}", "arabizi": f"gheir ma{E1}{E2}oo{E3}"}
            },
            "noun_of_place": {
                "affirmative": {"arabic": f"م{A1}{A2}{A3}", "arabizi": f"ma{E1}{E2}a{E3}"},
                "negative":    {"arabic": f"غير م{A1}{A2}{A3}", "arabizi": f"gheir ma{E1}{E2}a{E3}"}
            },
            "noun_of_tool": {
                "affirmative": {"arabic": f"م{A1}{A2}{A3}", "arabizi": f"mi{E1}{E2}a{E3}"},
                "negative":    {"arabic": f"غير م{A1}{A2}{A3}", "arabizi": f"gheir mi{E1}{E2}a{E3}"}
            },
            "masdar": {
                "affirmative": {"arabic": f"{A1}{A2}{A3}", "arabizi": f"{E1}{E2}a{E3}"},
                "negative":    {"arabic": f"عدم {A1}{A2}{A3}", "arabizi": f"3adam {E1}{E2}a{E3}"}
            },
            "mnemonic": {
                "affirmative": {"arabic": f"{A1}{A2}{A3}", "arabizi": f"{E1}e{E2}e{E3}"}
            }
        }

    def fetch_mit_dataset(self) -> list:
        url = "https://huggingface.co/datasets/iqrossed/quran-bil-quran/resolve/main/roots.jsonl"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx) as response:
                data = response.read().decode("utf-8")

            roots_data = []
            for line in data.strip().split("\n"):
                if not line:
                    continue
                try:
                    roots_data.append(json.loads(line))
                except Exception:
                    pass
            return roots_data
        except Exception:
            return [
                {"root": "خ ر ب", "meaning_en": "to be ruined, desolate, or destroyed"},
                {"root": "ص ب غ", "meaning_en": "to dye or color something; to immerse"},
                {"root": "ج ن ف", "meaning_en": "to incline, decline, or deviate"},
                {"root": "ك ت ب", "meaning_en": "to write or prescribe"},
                {"root": "س ف ك", "meaning_en": "to shed or pour"},
                {"root": "ع ل م", "meaning_en": "to know or perceive"},
            ]

    def build_database(self):
        dataset = self.fetch_mit_dataset()
        
        db_path = "master_arabic_roots_backend.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mother_arabic TEXT UNIQUE,
                sub_arabizi TEXT,
                sub_english TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nominals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_id INTEGER,
                category TEXT,
                polarity TEXT,
                arabic TEXT,
                arabizi TEXT,
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
                arabic TEXT,
                arabizi TEXT,
                FOREIGN KEY(root_id) REFERENCES roots(id)
            )
        """)
        
        cursor.execute("DELETE FROM conjugations")
        cursor.execute("DELETE FROM nominals")
        cursor.execute("DELETE FROM roots")

        for item in dataset:
            raw_root = item.get("root", "")
            mother_arabic = self.sanitize_arabic(raw_root).replace(" ", "")

            if not mother_arabic:
                continue

            raw_english = (
                item.get("summary_en")
                or item.get("meaning_en")
                or item.get("definition_en")
                or ""
            )

            if not self.validate_semantic_alignment(mother_arabic, raw_english):
                healed = False
                for alt_field in ["definition_en", "meaning_en", "summary_en"]:
                    alt_text = item.get(alt_field, "")
                    if alt_text and self.validate_semantic_alignment(mother_arabic, alt_text):
                        raw_english = alt_text
                        healed = True
                        break
                if not healed:
                    raw_english = self.lexical_backup.get(
                        mother_arabic,
                        f"to signify the primary conceptual action of {mother_arabic}",
                    )

            arabizi = self.generate_arabizi(raw_root)
            formatted_english = self.format_english_definition(raw_english, mother_arabic)

            ar_letters = list(mother_arabic.replace(" ", ""))
            en_letters = arabizi.split("-")

            if len(ar_letters) == 3 and len(en_letters) == 3:
                A1, A2, A3 = ar_letters[0], ar_letters[1], ar_letters[2]
                E1, E2, E3 = en_letters[0], en_letters[1], en_letters[2]

                try:
                    cursor.execute("""
                        INSERT INTO roots (mother_arabic, sub_arabizi, sub_english)
                        VALUES (?, ?, ?)
                    """, (mother_arabic, arabizi, formatted_english))
                    root_id = cursor.lastrowid
                except sqlite3.IntegrityError:
                    continue

                nominals = self.generate_nominals(A1, A2, A3, E1, E2, E3)
                nom_tuples = []
                for n_type, polarities in nominals.items():
                    for pol, scripts in polarities.items():
                        nom_tuples.append((root_id, n_type, pol, scripts["arabic"], scripts["arabizi"]))
                
                cursor.executemany("""
                    INSERT INTO nominals (root_id, category, polarity, arabic, arabizi)
                    VALUES (?, ?, ?, ?, ?)
                """, nom_tuples)

                dialectal_conjugations = self.generate_full_paradigm(A1, A2, A3, E1, E2, E3)
                conj_tuples = []
                for d in self.dialects:
                    d_code = d["code"]
                    d_conjugations = dialectal_conjugations.get(d_code, {})
                    for aspect, pol_dict in d_conjugations.items():
                        for pol, persons_dict in pol_dict.items():
                            for pid, scripts in persons_dict.items():
                                p_info = next((x for x in self.persons if x["id"] == pid), None)
                                if not p_info:
                                    p_info = next((x for x in self.imperative_persons if x["id"] == pid), {"p": "2", "n": "sg", "g": "m"})
                                
                                conj_tuples.append((
                                    root_id, d_code, aspect, pol, pid,
                                    p_info["p"], p_info["n"], p_info["g"],
                                    scripts["arabic"], scripts["arabizi"]
                                ))

                cursor.executemany("""
                    INSERT INTO conjugations (
                        root_id, dialect, aspect, polarity, person_id, person, number, gender, arabic, arabizi
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, conj_tuples)

        conn.commit()
        conn.close()


if __name__ == "__main__":
    pipeline = MITLicensedRootPipeline()
    pipeline.build_database()