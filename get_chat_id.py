"""بيطبع الـ chat_id بتاعك.

1. حط TELEGRAM_BOT_TOKEN في ملف .env
2. افتح البوت بتاعك على تيليجرام وابعتله /start
3. شغّل: python get_chat_id.py
"""

import os
import sys

import requests

from cinema_bot.config import load_env

load_env()
token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    sys.exit("حط TELEGRAM_BOT_TOKEN في ملف .env الأول")

data = None
for attempt in range(3):
    try:
        data = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
        break
    except requests.RequestException as e:
        # متطبعش رسالة الخطأ الأصلية: ممكن يبقى فيها الـ URL بالتوكن
        err = type(e).__name__
if data is None:
    sys.exit(f"مقدرتش أوصل لتيليجرام ({err}). جرب تاني كمان شوية.")
if not data.get("ok"):
    sys.exit(f"تيليجرام رفض: {data.get('description')} (اتأكد من التوكن)")

chats = {}
for upd in data.get("result", []):
    msg = upd.get("message") or upd.get("channel_post") or upd.get("my_chat_member") or {}
    chat = msg.get("chat")
    if chat:
        name = chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
        chats[chat["id"]] = (name, chat.get("type"))

if not chats:
    sys.exit("مفيش رسايل لسه. ابعت /start للبوت على تيليجرام وجرب تاني.")

for cid, (name, kind) in chats.items():
    print(f"TELEGRAM_CHAT_ID={cid}    # {name} ({kind})")
