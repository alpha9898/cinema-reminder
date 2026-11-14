"""الـ parsers على صفحات حقيقية محفوظة من المواقع (14 نوفمبر 2026)."""

from datetime import date
from pathlib import Path

from cinema_bot.sources import elcinema, premiere, scene

FX = Path(__file__).parent / "fixtures"


def fx(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


def test_elcinema_now():
    items = elcinema.parse_now(fx("elcinema_now.html"))
    assert len(items) == 15
    g = next(i for i in items if i.title == "Godzilla Minus Zero")
    assert g.source_id == "2098323"
    assert g.url == "https://elcinema.com/en/work/2098323/"
    assert g.poster.startswith("https://media0106.elcinema.com/uploads/_320x_")


def test_elcinema_release():
    assert elcinema.parse_release(fx("elcinema_work.html")) == date(2026, 11, 5)


def test_elcinema_showtimes():
    rows = elcinema.parse_showtimes(fx("elcinema_showtimes.html"))
    days = sorted({d for _, _, d, _ in rows})
    assert days[0] == date(2026, 11, 14) and len(days) == 5
    vox = [r for r in rows if r[0] == "3101353" and r[2] == date(2026, 11, 14)]
    assert vox and vox[0][3] == ["01:00 PM", "07:45 PM", "10:45 PM"]
    # المواعيد المخفية ورا "...More" (class="hide") بتتحسب، و"...More" نفسها لأ
    assert all(":" in t for r in rows for t in r[3])


def test_elcinema_theater():
    assert elcinema.parse_theater(fx("elcinema_theater.html")) == ("Vox Mall of Egypt Cinema", "Cairo")


def test_scene_now_only_now_showing_section():
    items = scene.parse_now(fx("scene_home.html"), "https://cfc.scenecinemas.com")
    assert len(items) == 17
    g = next(i for i in items if i.title == "Godzilla Minus Zero")
    assert g.source_id == "cfc.scenecinemas.com:godzilla-minus-zero"
    assert g.url == "https://cfc.scenecinemas.com/movie-details/godzilla-minus-zero.html"
    assert g.poster.startswith("https://statics.scenecinemas.com/posters/")
    assert not any("avengers" in i.title.lower() for i in items)  # Coming soon مش جوه


def test_scene_showtimes():
    shows = scene.parse_showtimes(fx("scene_showtimes.html"), date(2026, 11, 14))
    assert len(shows) == 1
    assert shows[0].cinema == "Scene Cinema - Cairo Festival City"
    assert shows[0].times == ["07:00 PM"]


def test_premiere_now_skips_presales():
    items = premiere.parse_now(fx("premiere_now.html"), date(2026, 11, 14))
    titles = {i.title for i in items}
    assert "Hadoota" in titles
    assert "Avengers: Doomsday" not in titles  # أول عرض 16 ديسمبر = حجز مسبق
    h = next(i for i in items if i.title == "Hadoota")
    assert h.url == "https://www.premiere-cinemas.com/en/movie-details/313/1"
    assert h.release == date(2026, 11, 11)  # 2026-11-10T22:00Z بتوقيت القاهرة
    assert h.poster.startswith("https://mifcentral-api.premiere-cinemas.com/uploads/")
    assert h.available_days[0] == date(2026, 11, 14)
