from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Show:
    """مواعيد فيلم في سينما واحدة في يوم واحد."""

    cinema: str
    day: date
    times: list[str]
    link: str | None = None  # لينك صفحة الفيلم في الفرع ده (لو موجود)


@dataclass
class Listing:
    """فيلم زي ما موقع واحد عارضه."""

    source: str  # "elcinema" | "premiere" | "scene"
    source_id: str
    title: str
    url: str
    poster: str | None = None
    release: date | None = None
    shows: list[Show] = field(default_factory=list)
    available_days: list[date] = field(default_factory=list)
    details_loaded: bool = False


def merge_shows(shows: list[Show]) -> list[Show]:
    """يدمج المواعيد المتكررة لنفس السينما في نفس اليوم (مع الحفاظ على الترتيب)."""
    merged: dict[tuple[str, date], Show] = {}
    for s in shows:
        key = (s.cinema, s.day)
        if key not in merged:
            merged[key] = Show(s.cinema, s.day, [], s.link)
        for t in s.times:
            if t not in merged[key].times:
                merged[key].times.append(t)
    return list(merged.values())
