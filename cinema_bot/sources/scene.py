"""Scene Cinemas / Galaxy Cinema: كل فرع ليه موقع بنفس الشكل (cfc.scenecinemas.com, moa.galaxy-cinema.com ...)."""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..http import Http
from ..models import Listing, Show, merge_shows

NAME = "scene"


def parse_now(html: str, branch_url: str) -> list[Listing]:
    """الأفلام اللي في قسم Now Showing بس (مش Coming Soon)."""
    soup = BeautifulSoup(html, "html.parser")
    section = None
    for sec in soup.select("div.glx_section"):
        h1 = sec.find("h1")
        if h1 and "now showing" in h1.get_text(" ", strip=True).lower():
            section = sec
            break
    if section is None:
        return []
    host = urlparse(branch_url).netloc
    out, seen = [], set()
    for item in section.select("li.film-cards-list-item"):
        a = item.select_one('a[href*="/movie-details/"]')
        if not a:
            continue
        url = a["href"]
        slug = re.search(r"/movie-details/([^/?#]+?)(?:\.html)?(?:[?#].*)?$", url)
        slug = slug.group(1) if slug else url
        if slug in seen:
            continue
        seen.add(slug)
        title_el = item.select_one(".card-title")
        title = title_el.get_text(" ", strip=True) if title_el else a.get("title", slug)
        img = item.select_one("img")
        poster = (img.get("data-src") or img.get("src")) if img else None
        if poster and "def-image" in poster:
            poster = None
        out.append(Listing(source=NAME, source_id=f"{host}:{slug}", title=title, url=url, poster=poster))
    return out


def parse_showtimes(html: str, day: date, link: str | None = None) -> list[Show]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for item in soup.select(".program_item"):
        branch_el = item.select_one(".branch")
        branch = branch_el.get_text(" ", strip=True) if branch_el else "Scene Cinemas"
        for block in item.select(".ex_stand_content"):
            label_el = block.select_one(".ex_stand")
            label = label_el.get_text(" ", strip=True) if label_el else ""
            times = [
                " ".join(a.get_text(" ", strip=True).split())
                for a in block.select("li a")
                if re.match(r"\d{1,2}:\d{2}", a.get_text(strip=True))
            ]
            if times:
                name = f"{branch} ({label})" if label and label.lower() != "standard" else branch
                out.append(Show(cinema=name, day=day, times=times, link=link))
    return out


def list_now_showing(http: Http, cfg: dict) -> list[Listing]:
    out, errors = [], []
    for branch in cfg.get("scene_branches", []):
        try:
            out.extend(parse_now(http.get_text(branch.rstrip("/") + "/"), branch))
        except Exception as e:  # فرع واقع ميوقفش الباقي
            errors.append(f"{branch}: {e}")
    if not out and errors:
        raise RuntimeError("; ".join(errors))
    return out


def load_details(listing: Listing, http: Http, cfg: dict, state: dict, today: date) -> None:
    shows = []
    days = max(int(cfg.get("days_to_show", 2)), 1)
    # بنبص على أيام زيادة شوية عشان لو الفيلم بيبدأ بكره أو بعده
    for i in range(days + 2):
        day = today + timedelta(days=i)
        url = f"{listing.url}?business_day={day:%d-%m-%Y}&ajax=1"
        try:
            shows.extend(parse_showtimes(http.get_text(url), day, link=listing.url))
        except Exception:
            continue
        if len({s.day for s in shows}) >= days:
            break
    listing.shows = merge_shows(shows)
    listing.details_loaded = True
