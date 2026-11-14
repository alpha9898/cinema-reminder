"""elCinema.com: بيجمع كل سينمات مصر (ومنه بنجيب مواعيد VOX و Premiere كمان)."""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..http import Http
from ..models import Listing, Show, merge_shows

NAME = "elcinema"
BASE = "https://elcinema.com"
NOW_URL = BASE + "/en/now/eg/?page={page}"
MAX_PAGES = 8


def parse_now(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for row in soup.select("div.row[id]"):
        m = re.fullmatch(r"w(\d+)", row.get("id", ""))
        if not m:
            continue
        work_id = m.group(1)
        a = row.select_one("h3 a")
        if not a:
            continue
        img = row.select_one(".thumbnail-wrapper img")
        poster = img.get("data-src") or img.get("src") if img else None
        if poster:
            # البوستر بمقاس أكبر لتيليجرام
            poster = poster.replace("/_315x420_", "/_320x_") if "/_315x420_" in poster else poster
        out.append(Listing(
            source=NAME,
            source_id=work_id,
            title=a.get_text(" ", strip=True),
            url=f"{BASE}/en/work/{work_id}/",
            poster=poster or None,
        ))
    return out


def parse_release(html: str) -> date | None:
    """أول 'Release Date' في صفحة الفيلم = تاريخ النزول في مصر."""
    m = re.search(
        r"Release Date:.*?release_day/(\d{2})-(\d{2})/.*?release_year/(\d{4})/",
        html,
        re.S,
    )
    if not m:
        return None
    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_showtimes(html: str) -> list[tuple[str, str, date, list[str]]]:
    """يرجع (theater_id, اسم السينما, اليوم, المواعيد)."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tab in soup.select("div.content[id^=wtheater]"):
        m = re.fullmatch(r"wtheater(\d{8})", tab.get("id", ""))
        if not m:
            continue
        day = datetime.strptime(m.group(1), "%Y%m%d").date()
        for row in tab.select("div.row"):
            link = None
            for a in row.select('a[href^="/en/theater/"]'):
                link = a
                break
            ul = row.select_one("ul.list-separator")
            if not link or not ul:
                continue
            tid = re.search(r"/en/theater/(\d+)", link["href"]).group(1)
            times = [
                " ".join(li.get_text(" ", strip=True).split())
                for li in ul.find_all("li", recursive=False)
                if not li.find("a") and re.match(r"\d{1,2}:\d{2}", li.get_text(strip=True))
            ]
            if times:
                out.append((tid, link.get_text(" ", strip=True), day, times))
    return out


def parse_theater(html: str) -> tuple[str | None, str | None]:
    """العنوان بيبقى: 'اسم السينما - المدينة - Egypt - Showtimes...'. بيرجع (الاسم الكامل, المدينة)."""
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return None, None
    parts = [" ".join(p.split()) for p in m.group(1).split(" - ")]
    for i, p in enumerate(parts):
        if p == "Egypt" and i > 0:
            name = " - ".join(parts[: i - 1]) or None
            return name, parts[i - 1]
    return None, None


def list_now_showing(http: Http, cfg: dict) -> list[Listing]:
    seen: dict[str, Listing] = {}
    for page in range(1, MAX_PAGES + 1):
        items = parse_now(http.get_text(NOW_URL.format(page=page)))
        new = [it for it in items if it.source_id not in seen]
        if not new:
            break
        for it in new:
            seen[it.source_id] = it
    if not seen:
        raise RuntimeError("elCinema: مفيش ولا فيلم في صفحة Now Playing (ممكن شكل الموقع اتغير)")
    return list(seen.values())


def _theater(tid: str, http: Http, state: dict) -> dict:
    """اسم السينما الكامل ومدينتها (بنحفظهم عشان منسألش تاني)."""
    cache = state.setdefault("elcinema_theaters", {})
    if tid not in cache:
        try:
            name, city = parse_theater(http.get_text(f"{BASE}/en/theater/{tid}/"))
        except Exception:
            return {}  # منعرفش: نعرض السينما أحسن ما نخفيها
        if not city:
            return {}
        cache[tid] = {"name": name, "city": city}
    return cache[tid]


def load_details(listing: Listing, http: Http, cfg: dict, state: dict) -> None:
    wid = listing.source_id
    try:
        listing.release = parse_release(http.get_text(f"{BASE}/en/work/{wid}/"))
    except Exception:
        pass
    cities = {c.lower() for c in cfg.get("cities", [])}
    shows = []
    for tid, name, day, times in parse_showtimes(http.get_text(f"{BASE}/en/work/{wid}/theater/eg")):
        info = _theater(tid, http, state)
        city = info.get("city")
        if cities and city and city.lower() not in cities:
            continue
        shows.append(Show(cinema=info.get("name") or name.rstrip(". "), day=day, times=times))
    listing.shows = merge_shows(shows)
    listing.details_loaded = True
