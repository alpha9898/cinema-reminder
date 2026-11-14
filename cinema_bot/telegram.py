from __future__ import annotations

import time

import requests

from .http import USER_AGENT

API = "https://api.telegram.org/bot{token}/{method}"
TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024


def split_text(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    """يقسم الرسالة الطويلة على أسطر من غير ما يقطع سطر في النص."""
    parts, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:  # سطر واحد أطول من الحد (نادر جداً)
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:limit])
            line = line[limit:]
        candidate = f"{cur}\n{line}" if cur else line
        if len(candidate) > limit:
            parts.append(cur)
            cur = line
        else:
            cur = candidate
    if cur.strip():
        parts.append(cur)
    return parts


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.session = requests.Session()

    def _call(self, method: str, data: dict, files: dict | None = None) -> dict:
        url = API.format(token=self.token, method=method)
        for attempt in range(4):
            try:
                r = self.session.post(url, data=data, files=files, timeout=60)
            except requests.RequestException as e:
                # رسالة الخطأ الأصلية ممكن يبقى فيها الـ URL بالتوكن، فبنكتب نوع الخطأ بس
                if attempt < 3:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise RuntimeError(f"Telegram {method}: network error ({type(e).__name__})") from None
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code == 429:
                time.sleep(body.get("parameters", {}).get("retry_after", 5) + 1)
                continue
            if body.get("ok"):
                return body
            if r.status_code >= 500 and attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            # متطبعش الـ URL لأن فيه التوكن
            raise RuntimeError(f"Telegram {method} failed: {r.status_code} {body.get('description', '')}")
        raise RuntimeError(f"Telegram {method} failed after retries")

    def send_text(self, text: str) -> None:
        for part in split_text(text):
            self._call("sendMessage", {
                "chat_id": self.chat_id,
                "text": part,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            })

    def send_photo(self, photo_url: str, caption: str) -> bool:
        """يبعت البوستر. لو تيليجرام معرفش يجيب الصورة من اللينك، بننزلها ونرفعها بنفسنا."""
        data = {"chat_id": self.chat_id, "caption": caption[:CAPTION_LIMIT], "parse_mode": "HTML"}
        try:
            self._call("sendPhoto", {**data, "photo": photo_url})
            return True
        except RuntimeError:
            pass
        try:
            img = requests.get(photo_url, headers={"User-Agent": USER_AGENT}, timeout=30)
            img.raise_for_status()
            self._call("sendPhoto", data, files={"photo": ("poster.jpg", img.content)})
            return True
        except Exception:
            return False


class DryRun:
    """بدل ما يبعت، بيطبع الرسايل (للتجربة)."""

    def send_text(self, text: str) -> None:
        for part in split_text(text):
            print("─" * 60)
            print(part)

    def send_photo(self, photo_url: str, caption: str) -> bool:
        print("═" * 60)
        print(f"[صورة] {photo_url}")
        print(caption)
        return True
