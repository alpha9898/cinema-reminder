"""رسايل تيليجرام (HTML)."""

from __future__ import annotations

from datetime import date
from html import escape

from .models import Film

MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def fmt_date(d: date) -> str:
    return f"{d.day} {MONTHS_AR[d.month - 1]} {d.year}"


def _link(url: str, text: str) -> str:
    return f'<a href="{escape(url, quote=True)}">{escape(text)}</a>'


def new_film(film: Film, release: date | None, branches: dict[str, list[str]], chains: dict) -> str:
    lines = ["🎬 <b>فيلم جديد نزل!</b>", "", f"<b>{escape(film.title)}</b>"]
    if release:
        lines.append(f"📅 تاريخ النزول: {fmt_date(release)}")
    lines.append("")
    links = [_link(film.url, "elCinema")]
    for key, ch in chains.items():
        if branches.get(key):
            lines.append(f"📍 <b>{escape(ch['title'])}</b>: {escape(' · '.join(branches[key]))}")
            links.append(_link(ch["link"], ch["title"]))
    lines += ["", "🔗 " + " · ".join(links)]
    return "\n".join(lines)


def started(tracked: int, waiting: int, chains: dict) -> str:
    names = " و ".join(ch["title"] for ch in chains.values())
    return (f"✅ <b>البوت شغال!</b>\n"
            f"هبعتلك أول ما فيلم جديد ينزل في {escape(names)}.\n\n"
            f"دلوقتي فيه {tracked} فيلم معروضين فيهم، و{waiting} فيلم تانيين لسه منزلوش عندهم "
            f"(هقولك لو وصلوا).")


def source_down(error: str) -> str:
    return ("⚠️ مش قادر أقرا <b>elCinema</b> دلوقتي.\n"
            f"<code>{escape(error[:300])}</code>\n"
            "هجرب تاني في التشغيل الجاي، وهقولك أول ما يرجع.")


def source_up() -> str:
    return "✅ <b>elCinema</b> رجع يشتغل تاني."
