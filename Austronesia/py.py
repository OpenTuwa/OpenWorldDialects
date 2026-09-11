import json
import re
import ssl
import sqlite3
import urllib.error
import urllib.request


# ============================================================================
# MALAY PURE-ROOT FIX
# Problem:
#   en-ms.txt is a word-to-word dictionary with NO part-of-speech tags.
#   Filtering English side by verbs.json is NOT enough, because English words
#   like "time / book / film / like / march / order" are noun/verb ambiguous,
#   while Malay side can be a noun (waktu, masa, kitab, filem, ibarat, mac),
#   an adjective (panjang, sejajar), or an already-affixed form
#   (bercakap, bekerja, tempahan, pesanan, susunan, terjumpa, dijumpai...).
#   Storing those as base_root and then applying meN- again produces
#   invalid double-affixed forms like "membercakap".
#
# Fix in this file:
#   1. extract_pure_root(): aggressive Malay stemmer (kata dasar) that strips
#      awalan (ber-/ter-/meN-/peN-/di-/ke-/se-/per-/be-...) and
#      akhiran (-kan/-i/-an/-nya/-lah/-kah/-ku/-mu...) with nasal restoration
#      (memukul->pukul, menulis->tulis, mengira->kira, menyapu->sapu...).
#   2. MALAY_VERB_ROOTS allowlist: only pure kata kerja dasar are accepted.
#      Bare noun roots (waktu, masa, kitab, filem, air, nama...) are rejected
#      even if their English gloss appears in verbs.json.
#   3. Collapsing: bercakap->cakap, bekerja->kerja, tempahan->tempah,
#      pesanan->pesan, susunan->susun, laporan/laporkan->lapor, etc. so the
#      `roots` table only stores pure verbs. Conjugation logic runs on pure.
#   4. get_standard_verb(): ber-class verbs use ber- (bercakap, berbincang,
#      bekerja, belajar), bare-class verbs stay bare (makan, pergi, tahu),
#      others use meN-. This prevents "membercakap" AND "memergi".
# ============================================================================

MALAY_VERB_ROOTS = {
    # existence / movement / posture (bare-class mostly)
    "ada", "pergi", "datang", "balik", "pulang", "sampai", "tiba",
    "keluar", "masuk", "naik", "turun", "panjat", "daki", "terjun",
    "selam", "renang", "jalan", "lari", "lompat", "loncat", "rangkak",
    "undur", "maju", "pusing", "belok", "lintas", "seberang",
    "henti", "rehat", "singgah", "berdiri", "duduk", "bangun", "bangkit",
    "baring", "tunduk", "jaga", "diam", "tinggal",
    # daily / eating / cooking / cleaning
    "makan", "minum", "tidur", "mandi", "basuh", "cuci", "gosok",
    "sapu", "pel", "lap", "bilas", "jemur", "lipat", "gantung",
    "bentang", "hampar", "masak", "goreng", "rebus", "bakar",
    "panggang", "kukus", "tumis", "hiris", "potong", "cincang",
    "kupas", "kopek", "hidang", "suap", "kunyah", "telan",
    "hirup", "teguk", "rasa", "jilat",
    # general action / work
    "kerja", "buat", "bina", "cipta", "baiki", "betul", "mula",
    "siap", "habis", "selesai", "ulang", "cuba", "usaha",
    "guna", "pakai", "buka", "tutup", "kunci", "selak", "umpil",
    "pecah", "belah", "koyak", "robek", "patah", "retak",
    # speech / cognition / perception
    "cakap", "bincang", "sembang", "borak", "bual", "runding",
    "kata", "sebut", "panggil", "jerit", "teriak", "laung", "pekik",
    "bisik", "tegur", "sapa", "tanya", "jawab", "balas",
    "pesan", "cerita", "nyanyi", "tari",
    "baca", "tulis", "lukis", "catat", "salin", "eja", "hafal",
    "ajar", "didik", "asuh", "latih", "uji", "kaji", "selidik", "siasat",
    "fikir", "renung", "tilik", "lihat", "tengok", "pandang", "tatap",
    "tenung", "jeling", "dengar", "pasang",
    "tahu", "kenal", "faham", "ingat", "lupa", "sangka", "duga",
    "agak", "ramal", "jangka", "percaya",
    # hands / body / force
    "angkat", "junjung", "pikul", "dukung", "bimbit", "jinjing",
    "tarik", "tolak", "dorong", "heret", "seret", "putar", "goyang",
    "goncang", "hayun", "lambung", "baling", "lempar", "campak",
    "lontar", "tangkap", "sambut", "pegang", "genggam",
    "sentuh", "raba", "ramas", "picit", "cubit", "cakar", "garu",
    "urut", "peluk", "cium", "gigit", "hisap", "sedut", "tiup", "hembus",
    "pukul", "ketuk", "tampar", "tendang", "sepak", "tikam", "tetak",
    "tembak", "panah", "bunuh",
    # transaction / social
    "beli", "jual", "bayar", "pinjam", "sewa", "tempah", "tawar",
    "beri", "bagi", "terima", "ambil", "bawa", "hantar", "kirim",
    "letak", "simpan", "sorok", "buang", "cari", "jumpa", "temu",
    "dapat", "atur", "susun", "agih", "bahagi", "kongsi",
    "tolong", "bantu", "nasihat", "cegah", "larang", "suruh", "arah",
    "paksa", "pujuk", "rayu", "minta", "pohon", "mohon",
    "janji", "sumpah", "tipu", "bohong", "tuduh", "fitnah",
    "puji", "hina", "maki", "kutuk", "doa",
    "sokong", "lapor",     "tunjuk", "papar", "siasat", "komen", "ulas",
    "rakam", "rekod", "catat", "kira", "hitung", "bilang",
    "terbang", "perhati",
    # emotion / stative (bare-class)
    "suka", "cinta", "sayang", "rindu", "benci", "marah", "takut",
    "malu", "segan", "tangis", "tawa", "senyum", "rajuk",
    "risau", "bimbang", "cemas", "sabar",
    # life / relations
    "hidup", "mati", "lahir", "sembuh", "kahwin", "nikah", "cerai",
    "pinang", "lamar", "tunang", "rujuk",
    # farming / craft
    "tanam", "semai", "tuai", "bajak", "cangkul", "siram",
    "petik", "kait", "tebang", "tebas", "ternak", "bela", "pelihara",
    "sembelih", "jahit", "sulam", "tenun", "anyam", "ukir", "pahat", "cat",
    # misc verified verbs (cover observed good data + common)
    "ubah", "suai", "ubahsuai", "serta", "perlu", "milik", "punya",
    "main", "kumpul", "baris", "layar", "belayar", "dayung", "kayuh",
    "pandu", "tunggang", "bonceng", "tamat", "mula", "tuntut", "tuduh",
    "tulis", "baca", "dengar", "lihat", "fikir", "rasa", "papar",
    # extended pure verbs (promoted from validated novel stems)
    "kagum", "alir", "angguk", "apung", "asing", "banding", "bayang",
    "bazir", "bekal", "benar", "biak", "bingkai", "bunyi", "buru",
    "cabar", "cabut", "cadang", "cahaya", "cambah", "campur", "cantum",
    "capai", "cukur", "dahulu", "debat", "dedah", "derita", "detik",
    "syak", "sedia", "elak", "selamat", "rendam", "lepas", "reput",
    "erat", "kesal", "galak", "ganti", "gegar", "gelak", "gembira",
    "gergaji", "gugur", "hadir", "hantu", "harap", "pancar", "lantun",
    "tapis", "patuk", "kawal", "nasihat", "desak", "pengaruh", "lancar",
    "pasti", "patuh", "peduli", "perang", "perah", "perintah", "pura",
    "pusar", "putus", "erang", "renjat", "ringkas", "rujuk", "saing",
    "salji", "sampuk", "santai", "sara", "sasar", "satu", "selaras",
    "sembunyi", "senam", "serang", "setuju", "simpul", "soal", "sukat",
    "surai", "taat", "taip", "teduh", "teka", "terus", "sambung",
    "timbun", "tingkat", "tumbuh", "tumpah", "ukur", "umum", "urus",
    "utama", "laksana", "lawat", "lindung", "lumba", "hasil", "hilang",
    "hias", "hidu", "hutang", "imbang", "jamin", "jana", "kurang",
    "kilau", "kitar", "kejar", "kelip", "kabung", "jampi", "joging",
    "kosong", "laju", "kemaskini", "rosak", "lambai", "langkah", "legar",
    "lengah", "lerai", "limpah", "lutut", "megah", "lucut", "aku",
    "meterai", "mimpi", "muat", "musnah", "nafas", "naung", "niat",
    "nyata", "sesal", "tambah",
    # Wiktionary-attested verbs (POS=verb in Kaikki; guards short-stem
    # over-stripping like mengecat->cat so these must be listed)
    "adu", "seka", "luncur", "cucuk", "kecap", "kisah", "asah", "tuju",
    "tinjau", "angkat",
}

# Verbs that MUST take ber-/be-/bel- in standard (intransitive).
# cakap->bercakap (NOT mencakap), bincang->berbincang (NOT membincang).
BER_VERBS = {
    "cakap", "bincang", "sembang", "borak", "bual", "runding",
    "jalan", "lari", "kerja", "main", "renang", "kumpul",
    "baris", "henti", "ajar",
    "bisik", "jerit", "teriak", "laung",
    "layar", "temu", "jumpa",
}

# Verbs used BARE in standard (no meN-). Prevents memergi/menduduk/menahu.
BARE_VERBS = {
    "ada", "pergi", "datang", "balik", "pulang", "sampai", "tiba",
    "duduk", "bangun", "tidur", "bangkit", "baring",
    "makan", "minum", "mandi", "jaga", "diam", "tinggal",
    "keluar", "masuk", "naik", "turun", "berdiri",
    "tahu", "kenal", "ingat", "lupa", "faham",
    "suka", "cinta", "sayang", "rindu", "benci", "marah", "takut",
    "malu", "segan", "tangis", "tawa", "senyum",
    "perlu", "milik", "punya", "terbang", "percaya",
}

# Pure roots that are NEVER verbs — explicit trash observed in DB.
NON_VERB_BLOCKLIST = {
    "waktu", "masa", "mac", "filem", "ibarat", "kitab", "sendiri",
    "nama", "nombor", "tempat", "nota", "taman", "lelaki",
    "air", "panjang", "belakang", "punggung", "hujung",
    "senarai", "sila", "sejajar",
    "orang", "manusia", "perempuan", "budak", "anak",
    "bapa", "ibu", "ayah", "emak", "abang", "kakak", "adik",
    "rumah", "kereta", "duit", "wang", "hari", "bulan", "tahun",
    "pagi", "petang", "malam", "siang",
    "besar", "kecil", "tinggi", "rendah", "jauh", "dekat",
    "lama", "baru", "cantik", "buruk", "baik", "jahat",
    "depan", "tepi", "tengah", "atas", "bawah",
    "apa", "siapa", "mana", "sini", "sana", "situ",
    "yang", "dan", "atau", "dengan", "kepada", "untuk", "kerana",
    "tangan", "barang", "kepala", "borang",
}

MONTH_BLOCK = {
    "jan", "feb", "mac", "apr", "mei", "jun", "jul", "ogos",
    "sep", "okt", "nov", "dis",
    "januari", "februari", "april", "julai",
    "september", "oktober", "november", "disember",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "october", "december",
}

# Colloquial aliases / morphophonemic fixes -> pure root.
SPECIAL_ALIASES = {
    "nemu": "temu",
    "ngomong": "cakap",
    "ngobrol": "bincang",
    "jawap": "jawab",  # jawapan = jawab + -an with b->p shift
}


def extract_pure_root(word: str):
    """Strip Malay affixes to kata dasar. Returns (stem, affixes_found)."""
    w = (word or "").lower().strip()
    if not w:
        return "", []
    if w in SPECIAL_ALIASES:
        return SPECIAL_ALIASES[w], ["alias"]
    affixes = []
    suffixes = ["kannya", "nya", "kan", "an", "i",
                "lah", "kah", "tah", "pun", "ku", "mu"]
    long_prefixes = ["memper", "diper", "menge",
                     "meny", "meng", "men", "mem",
                     "penge", "peny", "peng", "pen", "pem",
                     "ber", "ter", "per", "pel", "bel"]
    short_prefixes = ["be", "pe", "me", "di", "ke", "se", "te"]

    def strip_one_suffix(ww):
        # returns (new_w, suf) or (None, None); prefers verb-list remainder
        _all_pres = tuple(long_prefixes) + tuple(short_prefixes)
        cands = []
        for suf in suffixes:
            if ww.endswith(suf) and len(ww) - len(suf) >= 3:
                # Never strip root-final -i off a diphthong in a PREFIXLESS
                # word (abai->aba, capai->capa, cukai->cuka): the -ai/-oi
                # is the root. Prefixed words keep stripping (dijumpai ->
                # dijumpa -> jumpa), since the prefix phase resolves them.
                if suf == "i" and len(ww) >= 2 and ww[-2].lower() in "aeou" \
                        and not ww.startswith(_all_pres):
                    continue
                cands.append((ww[: -len(suf)], suf))
        if not cands:
            return None, None
        cands.sort(key=lambda t: (t[0] in MALAY_VERB_ROOTS, len(t[1])),
                   reverse=True)
        return cands[0]

    def strip_one_prefix(ww):
        # returns (new_w, pre) or (None, None)
        # long prefixes (>=3): strip, restoring nasals via verb-list vote;
        # short (2 chars): ONLY when remainder is a known verb.
        for pre in sorted(long_prefixes, key=len, reverse=True):
            if ww.startswith(pre) and len(ww) - len(pre) >= 3:
                if pre in ("menge", "penge"):
                    # menge- is only for monosyllabic roots (mengepam);
                    # mengerang = meng + erang: try both, prefer verb hit
                    rem_menge = ww[len(pre):]
                    base = "meng" if pre == "menge" else "pen"
                    rem_meng = ww[len(base):]
                    cands = [rem_menge, rem_meng]
                    if rem_meng and rem_meng[0] in "aeiou":
                        cands.append("k" + rem_meng)
                    best = None
                    for c in cands:
                        if c in MALAY_VERB_ROOTS:
                            best = c
                            break
                    if best is None:
                        continue  # let meng/pen branch try instead
                    return best, pre
                rem = ww[len(pre):]
                cands = [rem]
                if pre in ("mem", "pem") and rem and rem[0] in "aeiou":
                    # memukul->pukul (p-drop) vs memasak->masak (m-merge)
                    cands.extend(["p" + rem, "m" + rem])
                elif pre in ("men", "pen") and rem and rem[0] in "aeiou":
                    # menulis->tulis (t-drop) vs menasihati->nasihat (n-merge)
                    cands.extend(["t" + rem, "n" + rem])
                elif pre in ("meng", "peng") and rem and rem[0] in "aeiou":
                    cands.append("k" + rem)
                elif pre in ("meny", "peny") and rem:
                    cands.extend(["s" + rem, "ny" + rem])
                best = rem
                for c in cands:
                    if c in MALAY_VERB_ROOTS:
                        best = c
                        break
                if best not in MALAY_VERB_ROOTS:
                    # Defer to suffix-stripping when the remainder still
                    # carries a suffix tail (menasihati: strip -i first to
                    # get menasihat->nasihat, not asihat). Prevents
                    # asihat/esal/gant style fragments.
                    tail_suffixes = ("kannya", "nya", "kan", "an", "i",
                                     "lah", "kah", "tah", "pun", "ku", "mu")
                    if rem.endswith(tail_suffixes) and len(rem) >= 5:
                        return None, None
                return best, pre
        for pre in short_prefixes:
            if ww.startswith(pre) and len(ww) - len(pre) >= 3:
                rem = ww[len(pre):]
                if rem in MALAY_VERB_ROOTS:
                    return rem, pre
        return None, None

    # Alternating prefix-first loop with verb-list early stops.
    # Prefix-first prevents mengganti->gant (prefix meng->ganti wins before
    # root-final -i is touched); verb stops prevent bahagi->bahag,
    # pesan->pes/san, makan->mak over-stripping.
    for _ in range(4):
        if w in MALAY_VERB_ROOTS:
            break
        progressed = False
        nw, pre = strip_one_prefix(w)
        if nw is not None and not (w in MALAY_VERB_ROOTS):
            # long prefixes may strip even when remainder is novel, but
            # never reduce a known verb root
            w = nw
            affixes.append(f"{pre}-")
            progressed = True
            if w in MALAY_VERB_ROOTS:
                break
        nw2, suf = strip_one_suffix(w)
        if nw2 is not None and not (w in MALAY_VERB_ROOTS):
            w = nw2
            affixes.append(f"-{suf}")
            progressed = True
            if w in MALAY_VERB_ROOTS:
                break
        if not progressed:
            break

    if w in SPECIAL_ALIASES:
        w = SPECIAL_ALIASES[w]
        affixes.append("alias-fix")
    return w, affixes


def purify_malay_root(ms_word: str):
    """Return (pure_root or None, affixes, reason). Strict: pure must be verb."""
    w = (ms_word or "").lower().strip()
    # FATAL FIX: str.isalpha() is True for Jawi (Arabic-script) words, which
    # flooded the lexicon with ~900 script-duplicates of Latin entries.
    # Malay Rumi is pure ASCII; Jawi forms are rejected, not stemmed.
    if not w or not w.isascii() or not w.isalpha() or not (3 <= len(w) <= 12):
        return None, [], "bad-shape"
    if w in MONTH_BLOCK or w in NON_VERB_BLOCKLIST:
        return None, [], "noun-blocked"
    stem, affixes = extract_pure_root(w)
    # Tier 1: stemmed form is a known verb -> use stem (fixes bercakap->cakap)
    if stem in MALAY_VERB_ROOTS and stem not in NON_VERB_BLOCKLIST:
        return stem, affixes, "stem-verb"
    # Tier 2: original itself is a known verb -> keep original (bincang stays)
    if w in MALAY_VERB_ROOTS:
        return w, [], "base-verb"
    # Tier 3: affixed form with plausible novel stem (len>=4, not blocked)
    if affixes and stem not in NON_VERB_BLOCKLIST and stem not in MONTH_BLOCK \
            and 4 <= len(stem) <= 8 and stem.isalpha():
        return stem, affixes, "stem-novel"
    return None, affixes, "no-valid-root"


# Gloss patterns that mark a dictionary entry as a pointer/inflection rather
# than a real verb sense. Such entries are skipped (their lemma carries the
# meaning). Matched case-insensitively against the raw gloss.
META_GLOSS_PATTERNS = (
    "alternative", "misspelling", "abbreviation", "initialism", "acronym",
    "synonym of", "antonym of", "form of", "clipping", "short for",
    "ellipsis", "variant of", "passive of", "active of", "imperative of",
    "first-person", "second-person", "third-person", "plural of",
    "singular of", "present of", "past of", "participle of", "gerund of",
    "infinitive of",
)
EXISTENTIAL_BARE = {"there is", "there are", "there was", "there were"}


def normalize_kaikki_gloss(gloss: str) -> str:
    """Normalizes a Wiktionary verb gloss to our "to X" style.

    Returns "" when the gloss is a pointer ("alternative ... form of ..."),
    an inflection description ("first-person ... passive of ..."), or
    otherwise unusable. Wiktionary POS=verb is trusted, so bare phrases
    like "feign; pretend" safely become "to feign".
    """
    g = (gloss or "").strip()
    if not g:
        return ""
    low = g.lower()
    if any(k in low for k in META_GLOSS_PATTERNS):
        return ""
    for part in re.split(r"[;/]", g):
        p = part.strip().strip(".")
        if not p:
            continue
        if p.lower().startswith("to "):
            core = p[3:].strip()
        else:
            core = p
        # Cut subordinate clauses first, THEN validate: "There are, there
        # is." -> core "there are" -> existential -> skip (not "to there are").
        core = re.split(r"[,()]", core)[0].strip()
        if core.lower() in EXISTENTIAL_BARE:
            continue
        core = re.sub(r"\s+", " ", core)
        if not core or len(core.split()) > 6:
            continue
        if not re.match(r"^[a-zA-Z][a-zA-Z \-']*$", core):
            continue
        return "to " + core[:1].lower() + core[1:]
    return ""


def purify_malay_root_wiktionary(ms_word: str):
    """POS-gated variant of purify_malay_root for Wiktionary POS=verb entries.

    The dictionary already guarantees verbhood, so stems only need to be
    plausible kata dasar (correct length, not a blocked noun/month) — they
    do NOT need to sit in our hand-built verb list. This is the expansion
    path for genuine verbs our list does not cover yet.
    """
    w = (ms_word or "").lower().strip()
    if not w or not w.isascii() or not w.isalpha() or not (3 <= len(w) <= 12):
        return None, [], "bad-shape"
    if w in MONTH_BLOCK or w in NON_VERB_BLOCKLIST:
        return None, [], "noun-blocked"
    stem, affixes = extract_pure_root(w)
    if stem in MALAY_VERB_ROOTS and stem not in NON_VERB_BLOCKLIST:
        return stem, affixes, "wikt-stem-verb"
    if w in MALAY_VERB_ROOTS:
        return w, [], "wikt-base-verb"
    # Short stems reached only by stripping (berita->ita, pernah->nah)
    # are over-strip artifacts, never true roots: true 3-letter verbs
    # (cat, adu) arrive bare or sit in the verb list.
    if affixes and len(stem) < 4 and stem not in MALAY_VERB_ROOTS:
        return None, affixes, "wikt-frag"
    if stem not in NON_VERB_BLOCKLIST and stem not in MONTH_BLOCK \
            and 3 <= len(stem) <= 8 and stem.isalpha():
        return stem, affixes, "wikt-stem"
    return None, affixes, "no-valid-root"


def get_standard_verb(pure_root: str, phonology) -> str:
    """Correct standard imbuhan: ber- vs bare vs meN- (never double-affix)."""
    r = (pure_root or "").lower().strip()
    if not r:
        return ""
    # defensive: purify again so ber-/me- never stacks (membercakap impossible)
    purified, _, _ = purify_malay_root(r)
    if purified:
        r = purified
    else:
        # unknown word: strip obvious ber-/ter-/di- to avoid stacking,
        # then fall through to meN- rules
        stem, aff = extract_pure_root(r)
        if aff and 3 <= len(stem) <= 8:
            r = stem
    if r in BER_VERBS:
        if r == "ajar":
            return "belajar"
        if r == "kerja":
            return "bekerja"
        if r.startswith("r"):
            return "be" + r  # berenang, etc. (avoid double r)
        return "ber" + r  # bercakap, berbincang, berjalan...
    if r in BARE_VERBS:
        return r  # makan, pergi, tahu... stay bare
    return phonology.standard_prefix("me", r)


class MalayPhonologyEngine:
    """
    Advanced morphophonemic and phonological transformer for Malay dialects.
    Applies authentic, regional speech rules to base roots.
    NOTE: all inputs must be PURE kata dasar (see purify_malay_root).
    """

    @staticmethod
    def standard_prefix(prefix_type: str, root: str) -> str:
        """Applies Standard Malay Imbuhan (MeN- / PeN-) rules."""
        if not root:
            return ""
        first = root[0]
        if len(root) <= 3 and root not in ['ada', 'apa', 'air']:
            return f"m{'enge' if prefix_type == 'me' else 'penge'}{root}"
        if first in ['l', 'm', 'n', 'r', 'w', 'y']:
            return f"m{'e' if prefix_type == 'me' else 'pe'}{root}"
        if first in ['b', 'f', 'v']:
            return f"m{'em' if prefix_type == 'me' else 'pem'}{root}"
        if first == 'p':
            return f"m{'em' if prefix_type == 'me' else 'pem'}{root[1:]}"  # Drop P
        if first in ['c', 'd', 'j', 'z']:
            return f"m{'en' if prefix_type == 'me' else 'pen'}{root}"
        if first == 't':
            return f"m{'en' if prefix_type == 'me' else 'pen'}{root[1:]}"  # Drop T
        if first in ['a', 'e', 'i', 'o', 'u', 'g', 'h']:
            return f"m{'eng' if prefix_type == 'me' else 'peng'}{root}"
        if first == 'k':
            return f"m{'eng' if prefix_type == 'me' else 'peng'}{root[1:]}"  # Drop K
        if first == 's':
            return f"m{'eny' if prefix_type == 'me' else 'peny'}{root[1:]}"  # Drop S
        return f"m{'e' if prefix_type == 'me' else 'pe'}{root}"

    @staticmethod
    def colloquial_nasalization(root: str) -> str:
        first = root[0] if root else ""
        if first == 'p':
            return 'm' + root[1:]
        if first == 't':
            return 'n' + root[1:]
        if first == 'k':
            return 'ng' + root[1:]
        if first == 's':
            return 'ny' + root[1:]
        if first == 'c':
            return 'ny' + root[1:]
        return root

    @staticmethod
    def kelantan_shift(root: str) -> str:
        w = root.lower()
        w = re.sub(r'(an|am|ang)$', 'e', w)
        w = re.sub(r'a$', 'o', w)
        w = re.sub(r's$', 'h', w)
        w = re.sub(r'ar$', 'o', w)
        w = re.sub(r'r$', '', w)
        return w

    @staticmethod
    def terengganu_shift(root: str) -> str:
        w = root.lower()
        w = re.sub(r'a$', 'e', w)
        w = re.sub(r'([mn])$', 'ng', w)
        w = re.sub(r'r$', '', w)
        return w

    @staticmethod
    def kedah_shift(root: str) -> str:
        w = root.lower()
        w = re.sub(r'r$', 'q', w)
        w = re.sub(r'as$', 'aih', w)
        w = re.sub(r'is$', 'ih', w)
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
        # DEFENSIVE PURIFY: never conjugate an affixed/noun form.
        # bercakap->cakap so standard becomes bercakap, NOT membercakap.
        pure, _, _ = purify_malay_root(self.sanitize_root(root))
        if pure:
            root = pure
        else:
            root = self.sanitize_root(root)
            # last-resort destack to avoid member-/ter-... stacking
            stem, aff = extract_pure_root(root)
            if aff and 3 <= len(stem) <= 8 and stem.isalpha():
                root = stem
        if not root:
            return {}

        verb_std = get_standard_verb(root, self.phonology)
        verb_coll = self.phonology.colloquial_nasalization(root)
        verb_kel = self.phonology.kelantan_shift(root)
        verb_ter = self.phonology.terengganu_shift(root)
        verb_ked = self.phonology.kedah_shift(root)
        verb_base = root

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
                "verb": root,
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

            for aspect in ["past", "present", "future", "progressive"]:
                aff_dict, neg_dict = {}, {}

                for p_data in self.persons:
                    pid = p_data["id"]
                    p = grammar["pronouns"][pid]

                    aff_dict[pid] = grammar[aspect]["aff"].format(p=p, v=v)
                    neg_dict[pid] = grammar[aspect]["neg"].format(p=p, v=v)

                aspects_data[aspect] = {"affirmative": aff_dict, "negative": neg_dict}

            imp_aff, imp_neg = {}, {}
            for p_data in self.imperative_persons:
                pid = p_data["id"]
                p = grammar["pronouns"][pid]

                imp_aff[pid] = grammar["imperative"]["aff"].format(p=p, v=v)
                imp_neg[pid] = grammar["imperative"]["neg"].format(p=p, v=v)

            aspects_data["imperative"] = {"affirmative": imp_aff, "negative": imp_neg}
            dialect_conjugations[code] = aspects_data

        return dialect_conjugations

    def fetch_kaikki_malay_verbs(self) -> list:
        """Loads Wiktionary Malay verbs from the local Kaikki dump
        (kaikki-malay.jsonl, CC BY-SA via Wiktionary). Returns
        (word, "to X" gloss) pairs for POS=verb lemma entries only;
        inflected/pointer entries are skipped here (their lemmas carry
        the meaning). Missing file -> empty list (en-ms path still works).
        """
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "kaikki-malay.jsonl")
        if not os.path.exists(path):
            print("Kaikki Malay dump not found; skipping Wiktionary expansion.")
            return []
        pairs = []
        seen = set()
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    if entry.get("pos") != "verb":
                        continue
                    if (entry.get("lang_code") or entry.get("lang")) not in ("ms", "Malay"):
                        continue
                    senses = entry.get("senses", [])
                    if any("form-of" in s.get("tags", []) or
                           "inflection-template" in s.get("tags", []) or
                           s.get("form_of") for s in senses):
                        continue
                    word = (entry.get("word", "") or "").strip().lower()
                    if not word or word in seen:
                        continue
                    if not word.isascii():
                        continue  # Jawi-script duplicate of a Rumi entry
                    gloss = ""
                    for s in senses:
                        glosses = s.get("glosses") or []
                        if not glosses:
                            continue
                        gloss = normalize_kaikki_gloss(glosses[0])
                        if gloss:
                            break
                    if not gloss:
                        continue
                    seen.add(word)
                    pairs.append((word, gloss))
        except Exception as e:
            print(f"Kaikki Malay read failed ({e}); continuing without it.")
            return []
        print(f"Kaikki Malay: {len(pairs)} verb lemmas with usable glosses.")
        return pairs

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

        print("Intersecting datasets and purifying to pure kata dasar...")
        malay_dict = {}
        for line in data:
            parts = line.strip().split()
            if len(parts) == 2:
                en_w, ms_w = parts[0].lower(), parts[1].lower()

                if en_w in valid_english_verbs and ms_w != en_w:
                    if ms_w.isalpha() and 3 <= len(ms_w) <= 12:
                        if ms_w not in malay_dict:
                            malay_dict[ms_w] = []
                        if en_w not in malay_dict[ms_w]:
                            malay_dict[ms_w].append(en_w)

        print(f"Raw candidates after EN-verb filter: {len(malay_dict)}")
        # Purify + validate + collapse affixed variants to pure root
        pure_dict: dict = {}
        stats = {"stem-verb": 0, "base-verb": 0, "stem-novel": 0, "dropped": 0}
        dropped_samples = []

        def _merge(pure, meanings, reason):
            stats[reason] = stats.get(reason, 0) + 1
            if pure not in pure_dict:
                pure_dict[pure] = []
            for e in meanings:
                if e not in pure_dict[pure]:
                    pure_dict[pure].append(e)

        for ms_word, en_meanings in malay_dict.items():
            pure, affixes, reason = purify_malay_root(ms_word)
            if pure is None:
                stats["dropped"] += 1
                if len(dropped_samples) < 25:
                    dropped_samples.append(f"{ms_word}({','.join(en_meanings[:2])})[{reason}]")
                continue
            _merge(pure, en_meanings, reason)

        # EXPANSION: Wiktionary Malay verbs (Kaikki, CC BY-SA) via POS-gated
        # purifier. Wiktionary guarantees verbhood, so novel stems are
        # accepted after stemming + blocklist (no hand-list gating).
        for ms_word, gloss in self.fetch_kaikki_malay_verbs():
            pure, affixes, reason = purify_malay_root_wiktionary(ms_word)
            if pure is None:
                stats["dropped"] += 1
                continue
            # gloss is already "to X" style; store the bare verb for merging
            core = gloss[3:].strip()
            if core:
                _merge(pure, [core], reason)

        print(f"Purify stats: {stats}")
        print(f"Dropped samples: {dropped_samples[:25]}")
        print(f"Pure verb roots kept: {len(pure_dict)}")

        roots_data = []
        for ms_word in sorted(pure_dict.keys()):
            en_meanings = pure_dict[ms_word]
            meaning_str = "to " + " or ".join(en_meanings[:3])
            roots_data.append({"root": ms_word, "meaning_en": meaning_str})

        # No hard cap: the old [:2000] slice silently dropped valid verbs
        # once Wiktionary expansion pushed the lexicon past it (2219 roots
        # would have lost 219). 2-3k short roots stay shippable.
        print(f"Successfully filtered {len(roots_data)} pure verified roots.")
        return roots_data

    def build_database(self):
        dataset = self.fetch_open_source_dataset()
        # NOTE: must match index.html loader (Austronesia/Malay.sqlite)
        db_path = "Malay.sqlite"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("CREATE TABLE IF NOT EXISTS roots (id INTEGER PRIMARY KEY AUTOINCREMENT, base_root TEXT UNIQUE, meaning_english TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS conjugations (id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, dialect TEXT, aspect TEXT, polarity TEXT, person_id TEXT, person TEXT, number TEXT, phrase TEXT, FOREIGN KEY(root_id) REFERENCES roots(id))")

        cursor.execute("DELETE FROM conjugations")
        cursor.execute("DELETE FROM roots")

        for item in dataset:
            base_root = self.sanitize_root(item.get("root", ""))
            # No re-purification here: fetch already validated every root,
            # and re-running the purifier on STEMS (whose affix evidence was
            # consumed at fetch time, e.g. abaikan->abai) silently dropped
            # ~43% of the lexicon. Sanitize + shape check is sufficient.
            if not base_root or not base_root.replace(" ", "").isalpha():
                continue
            raw_english = item.get("meaning_en", "")
            if not base_root:
                continue

            try:
                cursor.execute("INSERT INTO roots (base_root, meaning_english) VALUES (?, ?)", (base_root, raw_english))
                root_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                continue

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

                            conj_tuples.append((root_id, d_code, aspect, pol, pid, p_info["p"], p_info["n"], phrase))

            cursor.executemany("INSERT INTO conjugations (root_id, dialect, aspect, polarity, person_id, person, number, phrase) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", conj_tuples)

        conn.commit()
        conn.close()
        print(f"Massive Dataset Built: '{db_path}'")


if __name__ == "__main__":
    pipeline = MalayLicensedRootPipeline()
    pipeline.build_database()
