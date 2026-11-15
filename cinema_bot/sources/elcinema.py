"""elCinema.com: لستة الأفلام المعروضة في مصر، والسينمات اللي بتعرض كل فيلم."""

from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from ..http import Http
from ..models import Film

BASE = "https://elcinema.com"
NOW_URL = BASE + "/en/now/eg/?page={page}"
MAX_PAGES = 8


def parse_now(html: str) -> list[Film]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for row in soup.select("div.row[id]"):
        m = re.fullmatch(r"w(\d+)", row.get("id", ""))
        if not m:
            continue
        a = row.select_one("h3 a")
        if not a:
            continue
        wid = m.group(1)
        img = row.select_one(".thumbnail-wrapper img")
        poster = (img.get("data-src") or img.get("src")) if img else None
        if poster and "/_315x420_" in poster:
            poster = poster.replace("/_315x420_", "/_320x_")  # مقاس أكبر لتيليجرام
        out.append(Film(id=wid, title=a.get_text(" ", strip=True), url=f"{BASE}/en/work/{wid}/", poster=poster or None))
    return out


def parse_release(html: str) -> date | None:
    """أول 'Release Date' في صفحة الفيلم = تاريخ النزول في مصر."""
    m = re.search(r"Release Date:.*?release_day/(\d{2})-(\d{2})/.*?release_year/(\d{4})/", html, re.S)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def parse_theaters(html: str) -> list[str]:
    """أسماء السينمات اللي بتعرض الفيلم (من صفحة 'Playing in which Cinemas')، من غير تكرار."""
    soup = BeautifulSoup(html, "html.parser")
    names: list[str] = []
    for a in soup.select('div.content[id^=wtheater] a[href^="/en/theater/"]'):
        name = a.get_text(" ", strip=True)
        if name and name not in names:
            names.append(name)
    return names


def short_branch(name: str, chain_words: list[str]) -> str:
    """'Vox Mall of Egypt Cinema' ← 'Mall of Egypt'، و'Premiere Americana MX4D ...' ← 'Americana MX4D'."""
    n = re.sub(r"\s*\.\.\.$", "", name).strip()
    n = re.sub(r"\bCinemas?\b", "", n, flags=re.I)
    for w in chain_words:
        n = re.sub(rf"\b{re.escape(w)}\b", "", n, flags=re.I)
    return " ".join(n.split()) or name


def branches_by_chain(theaters: list[str], chains: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name in theaters:
        low = name.lower()
        for key, ch in chains.items():
            words = ch.get("match", [])
            if any(w in low for w in words):
                short = short_branch(name, words)
                if short not in out.setdefault(key, []):
                    out[key].append(short)
                break
    return out


def list_now_showing(http: Http) -> list[Film]:
    seen: dict[str, Film] = {}
    for page in range(1, MAX_PAGES + 1):
        new = [f for f in parse_now(http.get_text(NOW_URL.format(page=page))) if f.id not in seen]
        if not new:
            break
        for f in new:
            seen[f.id] = f
    if not seen:
        raise RuntimeError("elCinema: مفيش ولا فيلم في صفحة Now Playing (ممكن شكل الموقع اتغير)")
    return list(seen.values())


def chain_branches(film_id: str, http: Http, chains: dict) -> dict[str, list[str]]:
    return branches_by_chain(parse_theaters(http.get_text(f"{BASE}/en/work/{film_id}/theater/eg")), chains)


def release_date(film_id: str, http: Http) -> date | None:
    try:
        return parse_release(http.get_text(f"{BASE}/en/work/{film_id}/"))
    except Exception:
        return None
