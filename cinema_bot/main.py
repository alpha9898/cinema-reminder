"""نقطة التشغيل: python -m cinema_bot.main [--dry-run] [--source elcinema] [--send-existing]"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import message, state as state_mod
from .config import load_config, load_env
from .http import Http
from .models import Listing
from .normalize import find_key
from .sources import elcinema, premiere, scene
from .telegram import DryRun, Telegram

CAIRO = ZoneInfo("Africa/Cairo")
SOURCES = ["elcinema", "scene", "premiere"]  # الترتيب مهم: الاسم والبوستر بيتاخدوا من أول واحد


def collect(http: Http, cfg: dict, today: date, only: list[str]) -> tuple[dict[str, list[Listing]], dict[str, str]]:
    found, errors = {}, {}
    for name in SOURCES:
        if only and name not in only:
            continue
        try:
            if name == "elcinema":
                found[name] = elcinema.list_now_showing(http, cfg)
            elif name == "scene":
                found[name] = scene.list_now_showing(http, cfg)
            elif name == "premiere":
                found[name] = premiere.list_now_showing(http, cfg, today)
            print(f"[{name}] {len(found[name])} فيلم")
        except Exception as e:
            errors[name] = f"{type(e).__name__}: {e}"
            print(f"[{name}] فشل: {errors[name]}", file=sys.stderr)
    return found, errors


def group(found: dict[str, list[Listing]], known: list[str]) -> dict[str, list[Listing]]:
    """يجمع نفس الفيلم من المواقع المختلفة تحت مفتاح واحد."""
    keys = list(known)
    groups: dict[str, list[Listing]] = {}
    for name in SOURCES:
        for l in found.get(name, []):
            k = find_key(l.title, keys)
            if k not in keys:
                keys.append(k)
            groups.setdefault(k, []).append(l)
    return groups


def load_details(listings: list[Listing], http: Http, cfg: dict, st: dict, today: date) -> None:
    for l in listings:
        if l.details_loaded:
            continue
        try:
            if l.source == "elcinema":
                elcinema.load_details(l, http, cfg, st)
            elif l.source == "scene":
                scene.load_details(l, http, cfg, st, today)
        except Exception as e:
            print(f"[{l.source}] مقدرتش أجيب تفاصيل {l.title}: {e}", file=sys.stderr)


def send_new_film(notifier, listings: list[Listing], cfg: dict, today: date) -> None:
    poster, caption, body = message.new_film(listings, cfg, today)
    sent_photo = bool(poster) and notifier.send_photo(poster, caption)
    notifier.send_text(body if sent_photo else f"{caption}\n\n{body}")


def run(args: argparse.Namespace) -> int:
    load_env()
    cfg = load_config()
    state_path = Path(args.state) if args.state else state_mod.DEFAULT_PATH
    st = state_mod.load(state_path)
    today = datetime.now(CAIRO).date()
    now_iso = datetime.now(CAIRO).isoformat(timespec="minutes")

    if args.dry_run:
        notifier = DryRun()
    else:
        token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat:
            print("لازم TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID (في .env أو في GitHub Secrets)", file=sys.stderr)
            return 2
        notifier = Telegram(token, chat)

    http = Http()
    found, errors = collect(http, cfg, today, args.source or [])
    send_errors: list[str] = []

    def notify(fn, *a) -> bool:
        try:
            fn(*a)
            return True
        except Exception as e:
            send_errors.append(str(e))
            print(f"فشل الإرسال: {e}", file=sys.stderr)
            return False

    # المواقع اللي وقعت أو رجعت
    for name, err in errors.items():
        if name not in st["failing"]:
            if notify(notifier.send_text, message.source_down(name, err)):
                st["failing"][name] = now_iso
    for name in found:
        if name in st["failing"] and notify(notifier.send_text, message.source_up(name)):
            del st["failing"][name]

    if not found:
        print("ولا موقع اشتغل، مش هغير حاجة.", file=sys.stderr)
        if not args.dry_run or args.save:
            state_mod.save(st, state_path)
        return 1

    announced: dict = st["announced"]
    groups = group(found, list(announced.keys()))
    first_run = not st["initialized"]
    # أول مرة موقع يشتغل (أول تشغيل، أو موقع كان واقع من الأول) بنسجل أفلامه من غير ما نبعتها،
    # عشان منبعتش كل الأفلام المعروضة أصلاً كأنها جديدة
    fresh = set() if args.send_existing else set(found) - set(st.get("seeded_sources", []))

    def remember(k: str, ls: list[Listing]) -> None:
        announced[k] = {"title": message.pick_title(ls), "sources": sorted({l.source for l in ls}),
                        "first_seen": today.isoformat(), "last_seen": today.isoformat()}

    quiet = 0
    for k, ls in groups.items():
        if k in announced:
            entry = announced[k]
            new_ls = [l for l in ls if l.source not in entry["sources"]]
            silent = [l for l in new_ls if l.source in fresh]
            loud = [l for l in new_ls if l.source not in fresh]
            entry["sources"] = sorted(set(entry["sources"]) | {l.source for l in silent})
            if loud:
                load_details(loud, http, cfg, st, today)
                if notify(notifier.send_text, message.more_sources(entry["title"], loud, cfg, today)):
                    entry["sources"] = sorted(set(entry["sources"]) | {l.source for l in loud})
                    print(f"+ {entry['title']}: {sorted({l.source for l in loud})}")
                time.sleep(0 if args.dry_run else 1)
        elif all(l.source in fresh for l in ls):
            remember(k, ls)
            quiet += 1
        else:
            load_details(ls, http, cfg, st, today)
            if notify(send_new_film, notifier, ls, cfg, today):
                remember(k, ls)
                print(f"جديد: {message.pick_title(ls)}")
            time.sleep(0 if args.dry_run else 1)

    if first_run and not args.send_existing:
        notify(notifier.send_text, message.first_run_summary([message.pick_title(ls) for ls in groups.values()]))
    if quiet:
        print(f"سجلت {quiet} فيلم من غير ما أبعتهم (أول قراية لـ {', '.join(sorted(fresh))}).")
    st["seeded_sources"] = sorted(set(st.get("seeded_sources", [])) | set(found))

    for k in groups:
        if k in announced:
            announced[k]["last_seen"] = today.isoformat()
    st["initialized"] = True
    state_mod.forget_old(st, today)

    if not args.dry_run or args.save:
        state_mod.save(st, state_path)
    return 1 if send_errors else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="بوت أفلام السينما المصرية")
    p.add_argument("--dry-run", action="store_true", help="اطبع الرسايل بدل ما تبعتها، ومتحفظش الـ state")
    p.add_argument("--save", action="store_true", help="مع --dry-run: احفظ الـ state برضه")
    p.add_argument("--source", action="append", choices=SOURCES, help="شغل مصدر معين بس (ممكن تكررها)")
    p.add_argument("--send-existing", action="store_true", help="في أول تشغيل: ابعت كل الأفلام المعروضة دلوقتي")
    p.add_argument("--state", help="مسار ملف الـ state (الافتراضي data/state.json)")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
