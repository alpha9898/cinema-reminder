"""الـ parsers على صفحات حقيقية محفوظة من elCinema (14 نوفمبر 2026)."""

from datetime import date
from pathlib import Path

from cinema_bot.sources import elcinema

FX = Path(__file__).parent / "fixtures"
CHAINS = {
    "vox": {"title": "VOX", "match": ["vox"], "link": "https://egy.voxcinemas.com/movies/whatson"},
    "premiere": {"title": "Premiere", "match": ["premiere"], "link": "https://www.premiere-cinemas.com/en/now-showing"},
}


def fx(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


def test_now_playing():
    films = elcinema.parse_now(fx("elcinema_now.html"))
    assert len(films) == 15
    g = next(f for f in films if f.title == "Godzilla Minus Zero")
    assert g.id == "2098323"
    assert g.url == "https://elcinema.com/en/work/2098323/"
    assert g.poster.startswith("https://media0106.elcinema.com/uploads/_320x_")


def test_release_date():
    assert elcinema.parse_release(fx("elcinema_work.html")) == date(2026, 11, 5)


def test_theaters_and_chains():
    theaters = elcinema.parse_theaters(fx("elcinema_showtimes.html"))
    assert len(theaters) == len(set(theaters)) == 14
    branches = elcinema.branches_by_chain(theaters, CHAINS)
    assert sorted(branches["vox"]) == ["City Centre Alexandria", "City Centre Almaza", "Mall of Egypt"]
    assert branches["premiere"] == ["IMAX"]


def test_short_branch_names():
    assert elcinema.short_branch("Vox Mall of Egypt Cinema", ["vox"]) == "Mall of Egypt"
    assert elcinema.short_branch("Premiere Americana MX4D ...", ["premiere"]) == "Americana MX4D"
    assert elcinema.short_branch("Premiere Point 90 Cinema", ["premiere"]) == "Point 90"


def test_other_cinemas_are_ignored():
    branches = elcinema.branches_by_chain(["City Stars Cinema", "Galaxy Cineplex Mall of Ara..."], CHAINS)
    assert branches == {}
