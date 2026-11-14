"""Premiere Cinemas: الأفلام من صفحة Now Showing.

الموقع مبني بـ Next.js وبيانات الأفلام مكتوبة جوه الصفحة نفسها (من غير API ولا تسجيل دخول).
مواعيد الساعات عندهم ورا API محتاج تسجيل، فبناخدها من elCinema لسينمات Premiere،
ومن هنا بناخد الأيام المتاحة واللينك والبوستر.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..http import Http
from ..models import Listing

NAME = "premiere"
SITE = "https://www.premiere-cinemas.com"
NOW_URL = SITE + "/en/now-showing"
MEDIA = "https://mifcentral-api.premiere-cinemas.com"
CAIRO = ZoneInfo("Africa/Cairo")


def _payload(html: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def _movie_arrays(payload: str):
    dec = json.JSONDecoder()
    for m in re.finditer(r'"movieData":(?=\[)', payload):
        try:
            arr, _ = dec.raw_decode(payload, m.end())
        except json.JSONDecodeError:
            continue
        if isinstance(arr, list):
            yield arr


def _cairo_date(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(CAIRO).date()
    except ValueError:
        return None


def parse_now(html: str, today: date) -> list[Listing]:
    out: dict[str, Listing] = {}
    for arr in _movie_arrays(_payload(html)):
        for mv in arr:
            mid = str(mv.get("movie_id", ""))
            title = (mv.get("movie_title") or "").strip()
            if not mid or not title or mid in out:
                continue
            days = sorted({
                d for d in (
                    _safe_date(x) for x in (mv.get("show_dates") or "").split(",") if x.strip()
                ) if d
            })
            # الفيلم "نزل" لو أول يوم عرض النهارده أو قبله (غير كده يبقى حجز مسبق)
            if not days or days[0] > today:
                continue
            art = mv.get("movie_original_artwork")
            out[mid] = Listing(
                source=NAME,
                source_id=mid,
                title=title,
                url=f"{SITE}/en/movie-details/{mid}/1",
                poster=(MEDIA + art) if art else None,
                release=_cairo_date(mv.get("movie_release_date")),
                available_days=[d for d in days if d >= today],
                details_loaded=True,
            )
    return list(out.values())


def _safe_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def list_now_showing(http: Http, cfg: dict, today: date) -> list[Listing]:
    items = parse_now(http.get_text(NOW_URL), today)
    if not items:
        raise RuntimeError("Premiere: مفيش أفلام في الصفحة (ممكن شكل الموقع اتغير)")
    return items
