"""الذاكرة بتاعة البوت: الأفلام اللي اتبعتت، المواقع اللي واقعة، ومدن سينمات elCinema."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .config import ROOT

DEFAULT_PATH = ROOT / "data" / "state.json"
FORGET_AFTER_DAYS = 180


def empty_state() -> dict:
    return {"version": 1, "initialized": False, "announced": {}, "failing": {}, "seeded_sources": [],
            "elcinema_theaters": {}}


def load(path: Path = DEFAULT_PATH) -> dict:
    if not path.exists():
        return empty_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    base = empty_state()
    base.update(data)
    return base


def save(state: dict, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def forget_old(state: dict, today: date) -> None:
    """ينسى الأفلام اللي بقالها 6 شهور مش معروضة، عشان الملف ميكبرش على الفاضي."""
    cutoff = (today - timedelta(days=FORGET_AFTER_DAYS)).isoformat()
    state["announced"] = {k: v for k, v in state["announced"].items() if v.get("last_seen", "") >= cutoff}
