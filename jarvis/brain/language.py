"""Bahasa: daftar ±100 bahasa Whisper, nama tujuan terjemahan, dan tebakan bahasa sebuah teks."""

from __future__ import annotations

import re

# Kode Whisper → nama Inggris (dipakai di prompt terjemahan). Semua bahasa yang dikenal Whisper.
WHISPER_LANGUAGES: dict[str, str] = {
    "af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "as": "Assamese", "az": "Azerbaijani",
    "ba": "Bashkir", "be": "Belarusian", "bg": "Bulgarian", "bn": "Bengali", "bo": "Tibetan",
    "br": "Breton", "bs": "Bosnian", "ca": "Catalan", "cs": "Czech", "cy": "Welsh",
    "da": "Danish", "de": "German", "el": "Greek", "en": "English", "es": "Spanish",
    "et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish", "fo": "Faroese",
    "fr": "French", "gl": "Galician", "gu": "Gujarati", "ha": "Hausa", "haw": "Hawaiian",
    "he": "Hebrew", "hi": "Hindi", "hr": "Croatian", "ht": "Haitian Creole", "hu": "Hungarian",
    "hy": "Armenian", "id": "Indonesian", "is": "Icelandic", "it": "Italian", "ja": "Japanese",
    "jw": "Javanese", "ka": "Georgian", "kk": "Kazakh", "km": "Khmer", "kn": "Kannada",
    "ko": "Korean", "la": "Latin", "lb": "Luxembourgish", "ln": "Lingala", "lo": "Lao",
    "lt": "Lithuanian", "lv": "Latvian", "mg": "Malagasy", "mi": "Maori", "mk": "Macedonian",
    "ml": "Malayalam", "mn": "Mongolian", "mr": "Marathi", "ms": "Malay", "mt": "Maltese",
    "my": "Burmese", "ne": "Nepali", "nl": "Dutch", "nn": "Nynorsk", "no": "Norwegian",
    "oc": "Occitan", "pa": "Punjabi", "pl": "Polish", "ps": "Pashto", "pt": "Portuguese",
    "ro": "Romanian", "ru": "Russian", "sa": "Sanskrit", "sd": "Sindhi", "si": "Sinhala",
    "sk": "Slovak", "sl": "Slovenian", "sn": "Shona", "so": "Somali", "sq": "Albanian",
    "sr": "Serbian", "su": "Sundanese", "sv": "Swedish", "sw": "Swahili", "ta": "Tamil",
    "te": "Telugu", "tg": "Tajik", "th": "Thai", "tk": "Turkmen", "tl": "Tagalog",
    "tr": "Turkish", "tt": "Tatar", "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek",
    "vi": "Vietnamese", "yi": "Yiddish", "yo": "Yoruba", "zh": "Chinese", "yue": "Cantonese",
}  # fmt: skip

# Nama bahasa dalam bahasa Indonesia (dan ejaan lain yang umum diucapkan) → kode.
_ID_ALIASES: dict[str, str] = {
    "inggris": "en", "indo": "id", "mandarin": "zh", "cina": "zh", "tionghoa": "zh",
    "china": "zh", "kanton": "yue", "jerman": "de", "spanyol": "es", "rusia": "ru",
    "prancis": "fr", "perancis": "fr", "jepang": "ja", "portugis": "pt", "turki": "tr",
    "polandia": "pl", "belanda": "nl", "arab": "ar", "swedia": "sv", "italia": "it",
    "finlandia": "fi", "vietnam": "vi", "ibrani": "he", "ukraina": "uk", "yunani": "el",
    "melayu": "ms", "ceko": "cs", "rumania": "ro", "romania": "ro", "denmark": "da",
    "hungaria": "hu", "norwegia": "no", "thailand": "th", "thai": "th", "kroasia": "hr",
    "bulgaria": "bg", "lituania": "lt", "wales": "cy", "slovakia": "sk", "persia": "fa",
    "farsi": "fa", "latvia": "lv", "serbia": "sr", "azerbaijan": "az", "slovenia": "sl",
    "estonia": "et", "makedonia": "mk", "islandia": "is", "armenia": "hy", "nepal": "ne",
    "bosnia": "bs", "albania": "sq", "georgia": "ka", "belarusia": "be", "amharik": "am",
    "filipina": "tl", "jawa": "jw", "sunda": "su", "punjabi": "pa", "burma": "my",
    "myanmar": "my", "korea": "ko", "latin": "la", "somalia": "so", "basque": "eu",
    "katalan": "ca", "malta": "mt", "yiddish": "yi", "swahili": "sw", "urdu": "ur",
}  # fmt: skip

# Nama yang diucapkan (Indonesia, Inggris, atau kode) → nama Inggris untuk prompt terjemahan.
LANG_NAMES: dict[str, str] = {
    **{name.lower(): name for name in WHISPER_LANGUAGES.values()},
    **{alias: WHISPER_LANGUAGES[code] for alias, code in _ID_ALIASES.items()},
    **{code: name for code, name in WHISPER_LANGUAGES.items() if len(code) > 1},
    "indonesia": "Indonesian",
}


def target_language(word: str) -> str | None:
    """'inggris' / 'english' / 'en' → 'English'; None bila bukan bahasa yang dikenal."""
    return LANG_NAMES.get(word.strip().lower())


def language_name(code: str) -> str:
    """Nama Inggris dari kode Whisper ('ja' → 'Japanese'); kode asing dikembalikan apa adanya."""
    return WHISPER_LANGUAGES.get(code, code)


# Bahasa yang sebaiknya tidak ikut deteksi otomatis "all": Melayu nyaris sama dengan Indonesia, dan
# Jawa/Sunda/Latin sering salah terdeteksi untuk ucapan Indonesia.
AMBIGUOUS = {"ms", "jw", "su", "la", "nn", "haw", "mi", "yue"}


def detect_candidates(setting: list[str]) -> list[str]:
    """Daftar kode bahasa untuk deteksi; ["all"] = semua bahasa Whisper yang tidak ambigu."""
    if "all" in setting:
        return ["id"] + [c for c in WHISPER_LANGUAGES if c != "id" and c not in AMBIGUOUS]
    codes = [c for c in setting if c in WHISPER_LANGUAGES]
    return codes or ["id", "en"]


_ID = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "ini", "itu", "saya", "aku", "kamu",
    "apa", "tidak", "bisa", "mau", "buka", "tutup", "tolong", "berapa", "bagaimana", "kenapa",
    "sudah", "belum", "ada", "akan", "pada", "adalah", "jam", "hari", "lagu", "nyalakan",
    "sedang", "persen", "baterai", "sekarang", "siap", "oke", "volume", "file", "folder",
}  # fmt: skip
_EN = {
    "the", "and", "is", "are", "to", "of", "for", "with", "this", "that", "what", "how", "why",
    "can", "you", "please", "open", "close", "play", "turn", "my", "me", "it", "in", "on",
    "time", "today", "tell", "show", "set", "do", "does", "who", "where", "when",
    "good", "morning", "evening", "night", "hello", "hi", "thanks", "thank", "everyone", "here",
    "there", "very", "your", "have", "has", "was", "were", "be", "will", "would", "not", "but",
    "from", "at", "by", "as", "an", "i", "we", "they", "he", "she", "if", "so", "sorry",
    "welcome", "sure", "yes", "capital", "weather", "name", "which", "than", "about",
    "it's", "its", "opening", "closed", "battery", "usage", "percent", "charging", "cancelled",
    "okay", "now", "couldn't", "isn't", "running", "am", "pm",
}  # fmt: skip
# Kata umum bahasa Latin lain (Spanyol/Prancis/Jerman/Portugis/Italia/Belanda): bila menang,
# teks bukan Indonesia/Inggris dan angkanya tidak boleh dieja dengan kata Indonesia.
_OTHER = {
    "el", "los", "las", "una", "por", "con", "que", "es", "está", "hola", "gracias", "muy",
    "le", "les", "des", "une", "est", "et", "pour", "avec", "bonjour", "merci", "je", "vous",
    "der", "die", "das", "und", "ist", "nicht", "ich", "ein", "eine", "mit", "danke", "guten",
    "não", "uma", "obrigado", "olá", "você", "il", "che", "sono", "grazie", "ciao", "buongiorno",
    "het", "een", "niet", "ik", "dank", "goedemorgen", "ja", "nee",
}  # fmt: skip


def guess(text: str) -> str:
    """'en', 'id', atau 'other' (aksara non-Latin atau Latin lain) untuk sebuah teks pendek."""
    letters = [c for c in text if c.isalpha()]
    if (
        letters
        and sum(c.isascii() or c in "áéíóúñüçãõâêôàèìòùäöß" for c in letters) < len(letters) * 0.7
    ):
        return "other"  # CJK, Arab, Thai, Cyrillic, Devanagari, ...
    words = re.findall(r"[a-zà-ÿ']+", text.lower())
    en = sum(w in _EN for w in words)
    idn = sum(w in _ID for w in words)
    other = sum(w in _OTHER for w in words)
    if other > max(en, idn):
        return "other"
    return "en" if en > idn else "id"
