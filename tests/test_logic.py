"""منطق "إيه الجديد" والرسايل، من غير إنترنت."""

from datetime import date

import pytest

from cinema_bot import main as bot
from cinema_bot import message
from cinema_bot.models import Listing, Show
from cinema_bot.normalize import find_key, normalize, same_film

TODAY = date(2026, 11, 14)
CFG = {
    "cities": ["Cairo", "Giza"],
    "days_to_show": 2,
    "chains": {
        "vox": {"title": "VOX Cinemas", "match": ["vox"], "link": "https://egy.voxcinemas.com/movies/whatson"},
        "premiere": {"title": "Premiere Cinemas", "match": ["premiere"], "link": "https://www.premiere-cinemas.com/en/now-showing"},
        "scene": {"title": "Scene / Galaxy Cinemas", "match": ["scene", "galaxy"], "link": "https://scenecinemas.com"},
    },
}


@pytest.mark.parametrize("a,b", [
    ("EBENZER", "Ebenezer"),
    ("Wala Kan Ala El-Bal", "Wala Kan Ala Albal"),
    ("The Cat in the Hat Ar", "The Cat In The Hat -Arabic DUB"),
    ("Matloub Aelyan", "Matloub Aaeleyan"),
    ("Hadoota (Arabic)", "Hadoota"),
])
def test_same_film(a, b):
    assert same_film(normalize(a), normalize(b))


@pytest.mark.parametrize("a,b", [
    ("Verity", "Venom"),
    ("Wildwood", "Whalefall"),
    ("The Cycle", "The Odyssey"),
])
def test_different_films(a, b):
    assert not same_film(normalize(a), normalize(b))


def test_find_key_reuses_known():
    assert find_key("EBENZER", ["ebenezer", "verity"]) == "ebenezer"
    assert find_key("Brand New Film", ["ebenezer"]) == "brand new film"


def el(title, wid, shows=()):
    return Listing("elcinema", wid, title, f"https://elcinema.com/en/work/{wid}/",
                   poster=f"https://img/{wid}.jpg", shows=list(shows), details_loaded=True)


def test_message_sections_split_by_chain():
    shows = [
        Show("Vox Mall of Egypt Cinema", TODAY, ["01:30 PM", "12:45 AM"]),
        Show("Premiere IMAX Cinema", TODAY, ["03:45 PM"]),
        Show("Cairo Festival Scene Cinema", TODAY, ["07:00 PM"]),
        Show("City Stars Cinema", TODAY, ["10:00 PM"]),
    ]
    own_scene = Listing("scene", "cfc:x", "X", "https://cfc.scenecinemas.com/movie-details/x.html",
                        shows=[Show("Scene Cinema - Cairo Festival City", TODAY, ["07:00 PM"])], details_loaded=True)
    poster, caption, body = message.new_film([el("X", "1", shows), own_scene], CFG, TODAY)
    assert poster == "https://img/1.jpg"
    assert "<b>X</b>" in caption
    assert "VOX Cinemas" in body and "1:30م · 12:45ص" in body
    assert "Premiere IMAX Cinema: 3:45م" in body
    # فرع Festival City يظهر مرة واحدة بس (من موقع Scene نفسه)
    assert "Cairo Festival Scene Cinema" not in body
    assert "Scene Cinema - Cairo Festival City: 7:00م" in body
    assert "City Stars Cinema" in body
    assert body.index("VOX") < body.index("Premiere") < body.index("Scene /") < body.index("سينمات تانية")


def test_html_is_escaped():
    _, caption, _ = message.new_film([el("Tom & Jerry <3", "9")], CFG, TODAY)
    assert "Tom &amp; Jerry &lt;3" in caption


class Recorder:
    def __init__(self):
        self.texts, self.photos = [], []

    def send_text(self, text):
        self.texts.append(text)

    def send_photo(self, url, caption):
        self.photos.append((url, caption))
        return True


@pytest.fixture
def harness(monkeypatch, tmp_path):
    rec = Recorder()
    found = {"value": {}}
    monkeypatch.setattr(bot, "DryRun", lambda: rec)
    monkeypatch.setattr(bot, "collect", lambda *a, **k: (found["value"], {}))
    monkeypatch.setattr(bot, "load_details", lambda *a, **k: None)
    monkeypatch.setattr(bot.time, "sleep", lambda s: None)
    state = tmp_path / "state.json"

    def run(listings, *extra):
        found["value"] = listings
        return bot.main(["--dry-run", "--save", "--state", str(state), *extra])

    return rec, run


def test_first_run_then_new_film_then_no_repeat(harness):
    rec, run = harness
    assert run({"elcinema": [el("Old Film", "1")]}) == 0
    assert len(rec.texts) == 1 and "البوت شغال" in rec.texts[0] and not rec.photos

    rec.texts.clear()
    assert run({"elcinema": [el("Old Film", "1"), el("Brand New", "2")]}) == 0
    assert len(rec.photos) == 1 and "Brand New" in rec.photos[0][1]

    rec.texts.clear(); rec.photos.clear()
    assert run({"elcinema": [el("Old Film", "1"), el("Brand New", "2")]}) == 0
    assert rec.texts == [] and rec.photos == []


def test_new_source_sends_follow_up_once(harness):
    rec, run = harness
    other = Listing("premiere", "5", "Other Movie", "https://p/5", details_loaded=True)
    run({"elcinema": [el("Film", "1"), el("Other Movie", "5")], "premiere": [other]})
    rec.texts.clear()
    pr = Listing("premiere", "7", "FILM", "https://www.premiere-cinemas.com/en/movie-details/7/1",
                 available_days=[TODAY], details_loaded=True)
    run({"elcinema": [el("Film", "1"), el("Other Movie", "5")], "premiere": [other, pr]})
    assert len(rec.texts) == 1 and "نزل كمان على Premiere Cinemas" in rec.texts[0]
    rec.texts.clear()
    run({"elcinema": [el("Film", "1")], "premiere": [pr]})
    assert rec.texts == []


def test_source_first_working_later_is_recorded_quietly(harness):
    rec, run = harness
    pr = Listing("premiere", "7", "Film", "https://p/7", details_loaded=True)
    run({"premiere": [pr]})  # elCinema واقع في أول تشغيل
    rec.texts.clear()
    # elCinema اشتغل: أفلامه الموجودة أصلاً متتبعتش كأنها جديدة
    run({"premiere": [pr], "elcinema": [el("Film", "1"), el("Already Showing", "2")]})
    assert rec.texts == [] and rec.photos == []
    # بس الفيلم الجديد فعلاً بعد كده بيتبعت
    run({"premiere": [pr], "elcinema": [el("Film", "1"), el("Already Showing", "2"), el("Fresh Release", "3")]})
    assert len(rec.photos) == 1 and "Fresh Release" in rec.photos[0][1]


def test_send_existing_on_first_run(harness):
    rec, run = harness
    run({"elcinema": [el("A", "1"), el("Bb film", "2")]}, "--send-existing")
    assert len(rec.photos) == 2


def test_source_down_warns_once_and_recovers(monkeypatch, tmp_path):
    rec = Recorder()
    monkeypatch.setattr(bot, "DryRun", lambda: rec)
    monkeypatch.setattr(bot, "load_details", lambda *a, **k: None)
    state = str(tmp_path / "s.json")
    ok = {"elcinema": [el("A", "1")]}

    monkeypatch.setattr(bot, "collect", lambda *a, **k: (ok, {"premiere": "HTTPError: 503"}))
    bot.main(["--dry-run", "--save", "--state", state])
    bot.main(["--dry-run", "--save", "--state", state])
    assert sum("مش قادر أقرا" in t for t in rec.texts) == 1

    monkeypatch.setattr(bot, "collect", lambda *a, **k: ({**ok, "premiere": []}, {}))
    bot.main(["--dry-run", "--save", "--state", state])
    assert any("رجع يشتغل" in t for t in rec.texts)
