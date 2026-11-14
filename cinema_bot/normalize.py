"""توحيد أسماء الأفلام عشان نعرف إن نفس الفيلم موجود في أكتر من موقع."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# كلمات بتتضاف للاسم وملهاش علاقة بالفيلم نفسه (لغة، نوع العرض...)
_NOISE = {
    "arabic", "ar", "english", "en", "japanese", "dubbed", "dub", "subtitled", "sub",
    "2d", "3d", "4dx", "imax", "mx4d", "screenx", "dolby", "atmos", "vip",
}

SIMILARITY = 0.86


def normalize(title: str) -> str:
    t = unicodedata.normalize("NFKD", title)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    words = [w for w in t.split() if w not in _NOISE]
    return " ".join(words) or title.strip().lower()


def _compact(key: str) -> str:
    return key.replace(" ", "")


def same_film(a: str, b: str) -> bool:
    """a و b أسماء بعد normalize."""
    if a == b:
        return True
    ca, cb = _compact(a), _compact(b)
    if ca == cb:
        return True
    if min(len(ca), len(cb)) < 5:
        return False
    return SequenceMatcher(None, ca, cb).ratio() >= SIMILARITY


def find_key(title: str, known: list[str]) -> str:
    """يرجع المفتاح الموجود لو الفيلم معروف، أو مفتاح جديد."""
    key = normalize(title)
    for k in known:
        if same_film(key, k):
            return k
    return key
