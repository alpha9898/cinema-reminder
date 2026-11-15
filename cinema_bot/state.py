"""ذاكرة البوت (data/state.json).

known[film_id] = {"title", "status", "first_seen", "last_seen"}
  status "notified": اتبعت عنه (أو كان معروض في VOX/Premiere قبل ما البوت يبدأ)
  status "pending":  معروض في مصر بس لسه مش في VOX/Premiere، بنفضل نشيك عليه
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .config import ROOT

DEFAULT_PATH = ROOT / "data" / "state.json"
VERSION = 2
FORGET_AFTER_DAYS = 180


def empty_state() -> dict:
    return {"version": VERSION, "initialized": False, "known": {}, "failing": {}}


def load(path: Path = DEFAULT_PATH) -> dict:
    if not path.exists():
        return empty_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    st = empty_state()
    if data.get("version") == VERSION:
        st.update(data)
    else:
        # نسخة قديمة من البوت: نبدأ من جديد (من غير ما نبعت الأفلام الموجودة)
        st["failing"] = data.get("failing", {})
    return st


def save(state: dict, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def forget_old(state: dict, today: date) -> None:
    cutoff = (today - timedelta(days=FORGET_AFTER_DAYS)).isoformat()
    state["known"] = {k: v for k, v in state["known"].items() if v.get("last_seen", "") >= cutoff}
