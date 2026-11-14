"""تكوين رسايل تيليجرام (HTML)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from html import escape
from urllib.parse import urlparse

from .models import Listing, Show

DAYS_AR = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
SITE_NAMES = {"elcinema": "elCinema", "premiere": "Premiere Cinemas", "scene": "Scene / Galaxy"}
SOURCE_ORDER = ["elcinema", "scene", "premiere"]

# كلمات عامة في أسماء فروع Scene/Galaxy مش بتفرق فرع عن التاني
_GENERIC = {"scene", "galaxy", "cinema", "cinemas", "cineplex", "the", "mall", "of", "city",
            "cairo", "giza", "egypt", "el", "dine", "in", "vip", "standard"}


def fmt_date(d: date) -> str:
    return f"{d.day} {MONTHS_AR[d.month - 1]} {d.year}"


def fmt_day(d: date) -> str:
    return f"{DAYS_AR[d.weekday()]} {d.day} {MONTHS_AR[d.month - 1]}"


def fmt_time(t: str) -> str:
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*([AaPp])", t)
    if not m:
        return t
    h, mi, ap = int(m.group(1)), m.group(2), m.group(3).lower()
    return f"{h}:{mi}{'ص' if ap == 'a' else 'م'}"


def _host(url: str) -> str:
    return urlparse(url).netloc.removeprefix("www.")


def _link(url: str, text: str | None = None) -> str:
    return f'<a href="{escape(url, quote=True)}">{escape(text or _host(url))}</a>'


@dataclass
class Section:
    title: str
    link: str
    shows: list[Show] = field(default_factory=list)
    note: str = ""
    available_days: list[date] = field(default_factory=list)


def _chain_of(cinema: str, chains: dict) -> str | None:
    name = cinema.lower()
    for key, ch in chains.items():
        if any(word in name for word in ch.get("match", [])):
            return key
    return None


def _tokens(name: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", name.lower())
    return {w for w in words if w not in _GENERIC and len(w) >= 3}


def _same_branch(a: str, b: str) -> bool:
    """'Scene Cinema - Cairo Festival City' و 'Cairo Festival Scene Cinema' نفس الفرع."""
    ta, tb = _tokens(a), _tokens(b)
    return any(x.startswith(y) or y.startswith(x) for x in ta for y in tb)


def build_sections(listings: list[Listing], cfg: dict) -> list[Section]:
    chains = cfg.get("chains", {})
    by_src: dict[str, list[Listing]] = {}
    for l in listings:
        by_src.setdefault(l.source, []).append(l)

    el_shows = [s for l in by_src.get("elcinema", []) for s in l.shows]
    buckets: dict[str | None, list[Show]] = {}
    for s in el_shows:
        buckets.setdefault(_chain_of(s.cinema, chains), []).append(s)

    sections: list[Section] = []
    from_el = "المواعيد من elCinema"

    if "vox" in chains and buckets.get("vox"):
        sections.append(Section(chains["vox"]["title"], chains["vox"]["link"], buckets["vox"], from_el))

    if "premiere" in chains:
        pr = by_src.get("premiere", [])
        pr_shows = buckets.get("premiere", [])
        if pr or pr_shows:
            link = pr[0].url if pr else chains["premiere"]["link"]
            sections.append(Section(
                chains["premiere"]["title"], link, pr_shows, from_el if pr_shows else "",
                available_days=pr[0].available_days if pr and not pr_shows else [],
            ))

    if "scene" in chains:
        sc = by_src.get("scene", [])
        own = [s for l in sc for s in l.shows]
        extra = [s for s in buckets.get("scene", []) if not any(_same_branch(s.cinema, o.cinema) for o in own)]
        if sc or extra:
            link = sc[0].url if sc else chains["scene"]["link"]
            sections.append(Section(chains["scene"]["title"], link, own + extra))

    others = buckets.get(None, [])
    el = by_src.get("elcinema", [])
    if el and others:
        sections.append(Section("سينمات تانية", el[0].url.rstrip("/") + "/theater/eg", others, "من elCinema"))
    return sections


def pick_days(sections: list[Section], today: date, n: int) -> list[date]:
    days = sorted({s.day for sec in sections for s in sec.shows if s.day >= today})
    return days[:n]


def render_section(sec: Section, days: list[date]) -> str:
    lines = [f"📍 <b>{escape(sec.title)}</b>"]
    shown = False
    for d in days:
        day_shows = sorted((s for s in sec.shows if s.day == d), key=lambda s: s.cinema.lower())
        if not day_shows:
            continue
        shown = True
        lines.append(f"<i>{fmt_day(d)}</i>")
        for s in day_shows:
            lines.append(f"• {escape(s.cinema)}: {' · '.join(fmt_time(t) for t in s.times)}")
    if not shown:
        if sec.available_days:
            lines.append("أيام العرض: " + "، ".join(fmt_day(d) for d in sec.available_days[:5]))
        else:
            lines.append("المواعيد على الموقع 👇")
    tail = f"🔗 {_link(sec.link)}"
    if sec.note and shown:
        tail += f" <i>({escape(sec.note)})</i>"
    lines.append(tail)
    return "\n".join(lines)


def _sorted(listings: list[Listing]) -> list[Listing]:
    return sorted(listings, key=lambda l: SOURCE_ORDER.index(l.source) if l.source in SOURCE_ORDER else 99)


def pick_title(listings: list[Listing]) -> str:
    return _sorted(listings)[0].title


def pick_poster(listings: list[Listing]) -> str | None:
    for l in _sorted(listings):
        if l.poster:
            return l.poster
    return None


def pick_release(listings: list[Listing]) -> date | None:
    for l in _sorted(listings):
        if l.release:
            return l.release
    return None


def new_film(listings: list[Listing], cfg: dict, today: date) -> tuple[str | None, str, str]:
    """يرجع (لينك البوستر, الـ caption, نص المواعيد)."""
    title = pick_title(listings)
    release = pick_release(listings)
    sources = sorted({l.source for l in listings}, key=SOURCE_ORDER.index)
    caption = [f"🎬 <b>فيلم جديد نزل السينما!</b>", "", f"<b>{escape(title)}</b>"]
    if release:
        caption.append(f"📅 تاريخ النزول: {fmt_date(release)}")
    caption.append("🌐 من: " + " · ".join(SITE_NAMES.get(s, s) for s in sources))

    sections = build_sections(listings, cfg)
    days = pick_days(sections, today, int(cfg.get("days_to_show", 2)))
    body = "\n\n".join(render_section(s, days) for s in sections)
    if not body:
        body = "\n".join(f"🔗 {_link(l.url, SITE_NAMES.get(l.source))}" for l in _sorted(listings))
    return pick_poster(listings), "\n".join(caption), f"🗓 <b>مواعيد {escape(title)}</b>\n\n{body}"


def more_sources(title: str, listings: list[Listing], cfg: dict, today: date) -> str:
    names = " و ".join(SITE_NAMES.get(s, s) for s in sorted({l.source for l in listings}, key=SOURCE_ORDER.index))
    sections = build_sections(listings, cfg)
    days = pick_days(sections, today, int(cfg.get("days_to_show", 2)))
    body = "\n\n".join(render_section(s, days) for s in sections)
    if not body:
        body = "\n".join(f"🔗 {_link(l.url)}" for l in _sorted(listings))
    return f"➕ <b>{escape(title)}</b> نزل كمان على {escape(names)}\n\n{body}"


def first_run_summary(titles: list[str]) -> str:
    lines = [f"✅ <b>البوت شغال!</b>", f"بتابع دلوقتي {len(titles)} فيلم معروضين في السينما.",
             "هبعتلك أول ما فيلم جديد ينزل 🍿", ""]
    lines += [f"• {escape(t)}" for t in sorted(titles, key=str.lower)]
    return "\n".join(lines)


def source_down(source: str, error: str) -> str:
    return (f"⚠️ مش قادر أقرا موقع <b>{escape(SITE_NAMES.get(source, source))}</b> دلوقتي.\n"
            f"<code>{escape(error[:300])}</code>\n"
            "هكمل بالمواقع التانية، وهقولك أول ما يرجع.")


def source_up(source: str) -> str:
    return f"✅ موقع <b>{escape(SITE_NAMES.get(source, source))}</b> رجع يشتغل تاني."
