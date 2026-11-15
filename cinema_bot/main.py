"""نقطة التشغيل: python -m cinema_bot.main [--dry-run] [--send-existing]

بيبعت رسالة لما فيلم يوصل لـ VOX أو Premiere (حسب config.yaml)، من بيانات elCinema.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import message, state as state_mod
from .config import load_config, load_env
from .http import Http
from .sources import elcinema
from .telegram import DryRun, Telegram

CAIRO = ZoneInfo("Africa/Cairo")


def run(args: argparse.Namespace) -> int:
    load_env()
    chains = load_config()["chains"]
    state_path = Path(args.state) if args.state else state_mod.DEFAULT_PATH
    st = state_mod.load(state_path)
    now = datetime.now(CAIRO)
    today = now.date().isoformat()

    if args.dry_run:
        notifier = DryRun()
    else:
        token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat:
            print("لازم TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID (في .env أو في GitHub Secrets)", file=sys.stderr)
            return 2
        notifier = Telegram(token, chat)

    errors: list[str] = []

    def notify(fn, *a) -> bool:
        try:
            fn(*a)
            return True
        except Exception as e:
            errors.append(str(e))
            print(f"فشل الإرسال: {e}", file=sys.stderr)
            return False

    def finish(code: int) -> int:
        if not args.dry_run or args.save:
            state_mod.save(st, state_path)
        return code

    http = Http()
    try:
        films = elcinema.list_now_showing(http)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"[elcinema] فشل: {err}", file=sys.stderr)
        if "elcinema" not in st["failing"] and notify(notifier.send_text, message.source_down(err)):
            st["failing"]["elcinema"] = now.isoformat(timespec="minutes")
        return finish(1)
    print(f"[elcinema] {len(films)} فيلم معروض")
    if "elcinema" in st["failing"] and notify(notifier.send_text, message.source_up()):
        del st["failing"]["elcinema"]

    known: dict = st["known"]
    # أول تشغيل: بنسجل الموجود من غير ما نبعته (إلا لو --send-existing)
    quiet = not st["initialized"] and not args.send_existing
    showing = {f.id for f in films}

    for film in films:
        entry = known.get(film.id)
        if entry:
            entry["last_seen"] = today
            if entry["status"] == "notified":
                continue
        try:
            branches = elcinema.chain_branches(film.id, http, chains)
        except Exception as e:
            print(f"مقدرتش أجيب سينمات {film.title}: {type(e).__name__}", file=sys.stderr)
            if quiet and not entry:  # في أول تشغيل: نعتبره قديم أحسن ما نبعته بالغلط بعدين
                known[film.id] = {"title": film.title, "first_seen": today, "last_seen": today, "status": "notified"}
            continue
        record = {"title": film.title, "first_seen": (entry or {}).get("first_seen", today), "last_seen": today}
        if not any(branches.values()):
            known[film.id] = {**record, "status": "pending"}
            continue
        if quiet:
            known[film.id] = {**record, "status": "notified"}
            continue
        text = message.new_film(film, elcinema.release_date(film.id, http), branches, chains)
        sent = notify(lambda: (film.poster and notifier.send_photo(film.poster, text)) or notifier.send_text(text))
        if sent:
            known[film.id] = {**record, "status": "notified"}
            print(f"جديد: {film.title} → {branches}")
        time.sleep(0 if args.dry_run else 1)

    # الأفلام اللي مستنيينها ونزلت من السينمات خلاص: مبقاش ليها لازمة
    for fid in [k for k, v in known.items() if v["status"] == "pending" and k not in showing]:
        del known[fid]

    if quiet:
        tracked = sum(1 for k, v in known.items() if k in showing and v["status"] == "notified")
        waiting = sum(1 for k, v in known.items() if k in showing and v["status"] == "pending")
        notify(notifier.send_text, message.started(tracked, waiting, chains))
        print(f"أول تشغيل: {tracked} فيلم في VOX/Premiere، و{waiting} لسه مستنيينهم.")

    st["initialized"] = True
    state_mod.forget_old(st, now.date())
    return finish(1 if errors else 0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="بوت أفلام VOX و Premiere")
    p.add_argument("--dry-run", action="store_true", help="اطبع الرسايل بدل ما تبعتها، ومتحفظش الـ state")
    p.add_argument("--save", action="store_true", help="مع --dry-run: احفظ الـ state برضه")
    p.add_argument("--send-existing", action="store_true", help="في أول تشغيل: ابعت كل الأفلام الموجودة دلوقتي")
    p.add_argument("--state", help="مسار ملف الـ state (الافتراضي data/state.json)")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
