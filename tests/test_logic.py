"""منطق "إمتى نبعت" والرسايل، من غير إنترنت."""

import json
from datetime import date

import pytest

from cinema_bot import main as bot
from cinema_bot import message
from cinema_bot.models import Film
from tests.test_parsers import CHAINS


def film(fid, title=None):
    return Film(fid, title or f"Film {fid}", f"https://elcinema.com/en/work/{fid}/", f"https://img/{fid}.jpg")


class Recorder:
    def __init__(self):
        self.texts, self.photos = [], []

    def send_text(self, text):
        self.texts.append(text)

    def send_photo(self, url, caption):
        self.photos.append((url, caption))
        return True


@pytest.fixture
def world(monkeypatch, tmp_path):
    """عالم وهمي: الأفلام المعروضة، وكل فيلم في أنهي سلاسل."""
    rec = Recorder()
    w = {"films": [], "branches": {}, "down": False}

    def list_now(http):
        if w["down"]:
            raise RuntimeError("HTTPError: 503")
        return w["films"]

    monkeypatch.setattr(bot, "DryRun", lambda: rec)
    monkeypatch.setattr(bot, "load_config", lambda: {"chains": CHAINS})
    monkeypatch.setattr(bot.elcinema, "list_now_showing", list_now)
    monkeypatch.setattr(bot.elcinema, "chain_branches", lambda fid, http, chains: w["branches"].get(fid, {}))
    monkeypatch.setattr(bot.elcinema, "release_date", lambda fid, http: date(2026, 11, 18))
    state = tmp_path / "state.json"

    def run(*extra):
        return bot.main(["--dry-run", "--save", "--state", str(state), *extra])

    return rec, w, run, state


def test_first_run_is_quiet_then_only_new_vox_premiere_films(world):
    rec, w, run, _ = world
    w["films"] = [film("1"), film("2")]
    w["branches"] = {"1": {"vox": ["Mall of Egypt"]}}  # 2 مش في VOX/Premiere
    assert run() == 0
    assert not rec.photos and len(rec.texts) == 1
    assert "البوت شغال" in rec.texts[0] and "1 فيلم معروضين فيهم" in rec.texts[0]

    rec.texts.clear()
    w["films"].append(film("3", "Brand New"))
    w["branches"]["3"] = {"premiere": ["IMAX", "Point 90"]}
    assert run() == 0
    assert len(rec.photos) == 1
    url, caption = rec.photos[0]
    assert url == "https://img/3.jpg"
    assert "Brand New" in caption and "Premiere</b>: IMAX · Point 90" in caption
    assert "18 نوفمبر 2026" in caption

    rec.photos.clear()
    assert run() == 0
    assert rec.photos == [] and rec.texts == []  # مفيش تكرار


def test_film_not_at_vox_or_premiere_is_sent_when_it_arrives(world):
    rec, w, run, _ = world
    w["films"] = [film("1")]
    run()
    rec.texts.clear()
    w["films"].append(film("9", "Arabic Film"))
    run()
    assert rec.photos == []  # في سينمات تانية بس: مفيش رسالة
    w["branches"]["9"] = {"vox": ["City Centre Almaza"]}
    run()
    assert len(rec.photos) == 1 and "Arabic Film" in rec.photos[0][1]


def test_pending_film_from_first_run_is_sent_later(world):
    rec, w, run, _ = world
    w["films"] = [film("1")]
    run()  # أول تشغيل: 1 مش في VOX/Premiere لسه
    w["branches"]["1"] = {"vox": ["Mall of Egypt"]}
    run()
    assert len(rec.photos) == 1


def test_send_existing(world):
    rec, w, run, _ = world
    w["films"] = [film("1"), film("2")]
    w["branches"] = {"1": {"vox": ["Mall of Egypt"]}, "2": {"premiere": ["IMAX"]}}
    run("--send-existing")
    assert len(rec.photos) == 2


def test_old_state_file_starts_quietly(world):
    rec, w, run, state = world
    state.write_text(json.dumps({"version": 1, "announced": {"x": {}}, "initialized": True}), encoding="utf-8")
    w["films"] = [film("1")]
    w["branches"] = {"1": {"vox": ["Mall of Egypt"]}}
    run()
    assert not rec.photos and "البوت شغال" in rec.texts[0]
    assert json.loads(state.read_text(encoding="utf-8"))["version"] == 2


def test_elcinema_down_warns_once_and_recovers(world):
    rec, w, run, _ = world
    w["films"] = [film("1")]
    run()
    w["down"] = True
    assert run() == 1
    run()
    assert sum("مش قادر أقرا" in t for t in rec.texts) == 1
    w["down"] = False
    run()
    assert any("رجع يشتغل" in t for t in rec.texts)


def test_html_is_escaped():
    text = message.new_film(film("1", "Tom & Jerry <3"), None, {"vox": ["Mall of Egypt"]}, CHAINS)
    assert "Tom &amp; Jerry &lt;3" in text
