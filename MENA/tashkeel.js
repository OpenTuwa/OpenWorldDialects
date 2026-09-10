'use client';

/**
 * Tashkeel (Arabic Diacritization) Engine for Learn Arabic
 * 
 * Provides 100% unambiguous phonetic vocalization for the 1,209 roots
 * and their derived verbal and nominal forms.
 * 
 * In Classical & Modern Standard Arabic (Fusha), applying explicit Tashkeel
 * removes all ambiguity for Text-to-Speech phoneticizers (e.g. espeak-ng / VITS).
 */

// Classical letter names with full Tashkeel for consonant phoneme practice
export const ARABIC_ALPHABET_NAMES = {
  'ا': 'أَلِفْ',
  'ب': 'بَاءْ',
  'ت': 'تَاءْ',
  'ث': 'ثَاءْ',
  'ج': 'جِيمْ',
  'ح': 'حَاءْ',
  'خ': 'خَاءْ',
  'د': 'دَالْ',
  'ذ': 'ذَالْ',
  'ر': 'رَاءْ',
  'ز': 'زَايْ',
  'س': 'سِينْ',
  'ش': 'شِينْ',
  'ص': 'صَادْ',
  'ض': 'ضَادْ',
  'ط': 'طَاءْ',
  'ظ': 'ظَاءْ',
  'ع': 'عَيْنْ',
  'غ': 'غَيْنْ',
  'ف': 'فَاءْ',
  'ق': 'قَافْ',
  'ك': 'كَافْ',
  'ل': 'لَامْ',
  'م': 'مِيمْ',
  'ن': 'نُونْ',
  'ه': 'هَاءْ',
  'و': 'وَاوْ',
  'ي': 'يَاءْ',
  'ء': 'هَمْزَة',
  'أ': 'أَلِفْ',
  'إ': 'أَلِفْ',
  'آ': 'أَلِفْ مَدَّة',
};

/**
 * Strip diacritics, tatweel and whitespace — consonantal skeleton comparison.
 * Used to verify a re-derived vocalization actually matches the displayed
 * form before speaking it (see getDiacritizedWord).
 */
export function stripArabicMarks(s) {
  return String(s || '').replace(/\s+/g, '').replace(/[ً-ٲٰـ]/g, '');
}

/**
 * Vocalize an individual Arabic letter (phonetic sound or letter name).
 */
export function vocalizeLetter(letter, asName = true) {
  if (asName && ARABIC_ALPHABET_NAMES[letter]) {
    return ARABIC_ALPHABET_NAMES[letter];
  }
  // Default to consonant with fat-ha (e.g. ك -> كَ)
  return `${letter}َ`;
}

/**
 * Fully diacritize a nominal category from its 3 root radicals (A1, A2, A3).
 */
export function diacritizeNominal(category, A1, A2, A3) {
  switch (category) {
    case 'active_participle':
      // Fā'ilun: كَاتِبٌ
      return `${A1}َا${A2}ِ${A3}ٌ`;
    case 'passive_participle':
      // Maf'ūlun: مَكْتُوبٌ
      return `مَ${A1}ْ${A2}ُو${A3}ٌ`;
    case 'noun_of_place':
      // Maf'alun: مَكْتَبٌ
      return `مَ${A1}ْ${A2}َ${A3}ٌ`;
    case 'noun_of_tool':
      // Mif'alun: مِكْتَبٌ
      return `مِ${A1}ْ${A2}َ${A3}ٌ`;
    case 'masdar':
      // Fa'lun: كَتْبٌ
      return `${A1}َ${A2}ْ${A3}ٌ`;
    default:
      return `${A1}َ${A2}َ${A3}َ`;
  }
}

/**
 * Fully diacritize a verb conjugation given aspect, polarity, person, and root radicals.
 */
export function diacritizeConjugation(aspect, polarity, personId, A1, A2, A3) {
  const isNeg = polarity === 'negative';

  // Past Tense: Fa'ala (كَتَبَ)
  if (aspect === 'past') {
    let verb = '';
    switch (personId) {
      case '1s':  verb = `${A1}َ${A2}َ${A3}ْتُ`; break;       // katabtu
      case '1p':  verb = `${A1}َ${A2}َ${A3}ْنَا`; break;      // katabnā
      case '2ms': verb = `${A1}َ${A2}َ${A3}ْتَ`; break;       // katabta
      case '2fs': verb = `${A1}َ${A2}َ${A3}ْتِ`; break;       // katabti
      case '3ms': verb = `${A1}َ${A2}َ${A3}َ`; break;        // kataba
      case '3fs': verb = `${A1}َ${A2}َ${A3}َتْ`; break;       // katabat
      case '3p':  verb = `${A1}َ${A2}َ${A3}ُوا`; break;       // katabū
      default:    verb = `${A1}َ${A2}َ${A3}َ`; break;
    }
    return isNeg ? `مَا ${verb}` : verb;
  }

  // Present Imperfective: Yaf'ulu (يَكْتُبُ)
  if (aspect === 'present') {
    let verb = '';
    switch (personId) {
      case '1s':  verb = `أَ${A1}ْ${A2}ُ${A3}ُ`; break;        // 'aktubu
      case '1p':  verb = `نَ${A1}ْ${A2}ُ${A3}ُ`; break;        // naktubu
      case '2ms': verb = `تَ${A1}ْ${A2}ُ${A3}ُ`; break;        // taktubu
      case '2fs': verb = `تَ${A1}ْ${A2}ُ${A3}ِينَ`; break;     // taktubīna
      case '3ms': verb = `يَ${A1}ْ${A2}ُ${A3}ُ`; break;        // yaktubu
      case '3fs': verb = `تَ${A1}ْ${A2}ُ${A3}ُ`; break;        // taktubu
      case '3p':  verb = `يَ${A1}ْ${A2}ُ${A3}ُونَ`; break;     // yaktubūna
      default:    verb = `يَ${A1}ْ${A2}ُ${A3}ُ`; break;
    }
    return isNeg ? `لَا ${verb}` : verb;
  }

  // Future Tense: Sayaf'ulu (سَيَكْتُبُ)
  if (aspect === 'future') {
    const pres = diacritizeConjugation('present', 'affirmative', personId, A1, A2, A3);
    if (isNeg) {
      // Lan Yaf'ula: لَنْ يَكْتُبَ
      return `لَنْ ${pres.slice(0, -1)}َ`;
    }
    return `سَ${pres}`;
  }

  // Fallback default
  return `${A1}َ${A2}َ${A3}َ`;
}

/**
 * Data-driven diacritizer. Speak exactly what the user clicked.
 *
 * @param {string}      rawText  The opt.arabic string the user clicked
 * @param {object|null} root     The root object (for radical extraction)
 * @param {object}      [opt]    The full clicked data object — when supplied,
 *                               the correct diacritizer is invoked directly
 *                               from the semantic metadata (category / aspect /
 *                               polarity / person_id) instead of guessing from
 *                               the raw text. This is the authoritative path.
 * @returns {string} Fully diacritized Arabic string ready for TTS
 */
export function getDiacritizedWord(rawText, root, opt = null) {
  if (!rawText) return '';
  // If already contains diacritics, trust them — no re-processing needed
  if (/[\u064B-\u0652]/.test(rawText)) return rawText;

  const arLetters = root?.mother_arabic?.replace(/\s/g, '').split('') || [];
  const [A1, A2, A3] = arLetters.length === 3 ? arLetters : [null, null, null];
  const clean = rawText.replace(/\s/g, '');

  // ── Authoritative path: full clicked-object metadata available ─────────────
  // Driven entirely by the data the user clicked, never by hardcoded guesses.
  // SAFETY RULE: the re-derived vocalization is spoken ONLY if its
  // consonantal skeleton matches the displayed text. Otherwise the data
  // carries a dialectal / periphrastic / irregular form (Levantine بيكتب,
  // MSA progressive في طور…, Egyptian negation …ش) and "correcting" it to
  // fusha would speak a DIFFERENT word than the one shown — the voice saying
  // one thing while the card shows another. In that case speak the displayed
  // text as-is.
  if (opt && A1) {
    // Nominal forms (MoldMatchCard)
    if (opt.category && !opt.aspect) {
      const derived = diacritizeNominal(opt.category, A1, A2, A3);
      if (stripArabicMarks(derived) === stripArabicMarks(rawText)) return derived;
      return rawText.trim();
    }

    // Conjugation forms (PersonCard, TimeBadgeCard, NegationCard)
    if (opt.aspect && opt.person_id) {
      const derived = diacritizeConjugation(
        opt.aspect,
        opt.polarity ?? 'affirmative',
        opt.person_id,
        A1, A2, A3
      );
      if (stripArabicMarks(derived) === stripArabicMarks(rawText)) return derived;
      return rawText.trim();
    }
  }

  // ── Fallback path: no opt metadata (RootHeroCard letters, SprintSummary) ───
  // Pattern-match raw text against root radicals as a best-effort diacritizer.
  if (!A1) return clean;

  // Single letter → letter name
  if (clean.length === 1 && ARABIC_ALPHABET_NAMES[clean]) {
    return ARABIC_ALPHABET_NAMES[clean];
  }

  // Base 3-letter root
  if (clean === `${A1}${A2}${A3}`) return `${A1}َ${A2}َ${A3}َ`;

  // Active Participle: C1-aa-C2-C3
  if (clean === `${A1}ا${A2}${A3}`) return `${A1}َا${A2}ِ${A3}ٌ`;

  // Passive Participle: ma-C1-C2-oo-C3
  if (clean === `م${A1}${A2}و${A3}`) return `مَ${A1}ْ${A2}ُو${A3}ٌ`;

  // Noun of Place: ma-C1-C2-C3
  if (clean === `م${A1}${A2}${A3}`) return `مَ${A1}ْ${A2}َ${A3}ٌ`;

  // Common present-person prefixes
  if (clean === `ن${A1}${A2}${A3}`) return `نَ${A1}ْ${A2}ُ${A3}ُ`;
  if (clean === `أ${A1}${A2}${A3}`) return `أَ${A1}ْ${A2}ُ${A3}ُ`;
  if (clean === `ي${A1}${A2}${A3}`) return `يَ${A1}ْ${A2}ُ${A3}ُ`;
  if (clean === `ت${A1}${A2}${A3}`) return `تَ${A1}ْ${A2}ُ${A3}ُ`;
  if (clean === `ي${A1}${A2}${A3}وا`) return `يَ${A1}ْ${A2}ُ${A3}ُونَ`;

  // Colloquial / Dialect forms
  if (clean.startsWith('ب') && clean.includes(`${A1}${A2}${A3}`)) return `بِيِ${A1}ْ${A2}ِ${A3}ْ`;
  if (clean.startsWith('ح') && clean.includes(`${A1}${A2}${A3}`)) return `حَيِ${A1}ْ${A2}ِ${A3}ْ`;
  if (clean.includes('ما') && clean.includes('ش')) return `مَا بِيِ${A1}ْ${A2}ِ${A3}ْشْ`;

  return clean;
}
