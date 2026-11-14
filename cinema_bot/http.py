from __future__ import annotations

import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


class Http:
    """جلسة HTTP مؤدبة: بتعيد المحاولة لو حصل خطأ، ومستنية شوية بين الطلبات لنفس الموقع."""

    def __init__(self, delay: float = 0.5, timeout: float = 25):
        self.delay = delay
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        retry = Retry(total=3, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def get_text(self, url: str) -> str:
        host = urlparse(url).netloc
        wait = self._last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.session.get(url, timeout=self.timeout)
        finally:
            self._last[host] = time.monotonic()
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        return r.text
