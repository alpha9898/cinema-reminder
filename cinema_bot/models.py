from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Film:
    """فيلم معروض دلوقتي على elCinema."""

    id: str
    title: str
    url: str
    poster: str | None = None
