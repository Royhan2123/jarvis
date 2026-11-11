"""Bahasa: nama bahasa tujuan terjemahan dan tebakan bahasa sebuah teks (Indonesia / Inggris)."""

from __future__ import annotations

import re

# Nama yang diucapkan (Indonesia & Inggris) → nama bahasa untuk prompt terjemahan.
LANG_NAMES: dict[str, str] = {
    "inggris": "English", "english": "English", "en": "English",
    "indonesia": "Indonesian", "indonesian": "Indonesian", "indo": "Indonesian",
    "jepang": "Japanese", "japanese": "Japanese",
    "korea": "Korean", "korean": "Korean",
    "mandarin": "Chinese", "cina": "Chinese", "china": "Chinese", "chinese": "Chinese",
    "arab": "Arabic", "arabic": "Arabic",
    "jerman": "German", "german": "German",
    "prancis": "French", "perancis": "French", "french": "French",
    "spanyol": "Spanish", "spanish": "Spanish",
    "belanda": "Dutch", "dutch": "Dutch",
    "portugis": "Portuguese", "portuguese": "Portuguese",
    "rusia": "Russian", "russian": "Russian",
    "italia": "Italian", "italian": "Italian",
    "jawa": "Javanese", "javanese": "Javanese",
    "sunda": "Sundanese", "sundanese": "Sundanese",
}  # fmt: skip


def target_language(word: str) -> str | None:
    """'inggris' → 'English'; None bila bukan bahasa yang dikenal."""
    return LANG_NAMES.get(word.strip().lower())


_ID = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "ini", "itu", "saya", "aku", "kamu",
    "apa", "tidak", "bisa", "mau", "buka", "tutup", "tolong", "berapa", "bagaimana", "kenapa",
    "sudah", "belum", "ada", "akan", "pada", "adalah", "jam", "hari", "lagu", "nyalakan",
}  # fmt: skip
_EN = {
    "the", "and", "is", "are", "to", "of", "for", "with", "this", "that", "what", "how", "why",
    "can", "you", "please", "open", "close", "play", "turn", "my", "me", "it", "in", "on",
    "time", "today", "tell", "show", "set", "do", "does", "who", "where", "when",
    "good", "morning", "evening", "night", "hello", "hi", "thanks", "thank", "everyone", "here",
    "there", "very", "your", "have", "has", "was", "were", "be", "will", "would", "not", "but",
    "from", "at", "by", "as", "an", "i", "we", "they", "he", "she", "if", "so", "sorry",
    "welcome", "sure", "yes", "capital", "weather", "name", "which", "than", "about",
}  # fmt: skip


def guess(text: str) -> str:
    """'en' bila teks lebih banyak memuat kata Inggris umum daripada Indonesia, selain itu 'id'."""
    words = re.findall(r"[a-z']+", text.lower())
    en = sum(w in _EN for w in words)
    idn = sum(w in _ID for w in words)
    return "en" if en > idn else "id"
