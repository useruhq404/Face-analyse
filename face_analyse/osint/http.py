"""Client HTTP partagé : délais, nouvelles tentatives, User-Agent identifié,
limitation de débit par hôte (politesse envers les API publiques)."""

from __future__ import annotations

import threading
import time
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from face_analyse import __version__

USER_AGENT = f"FaceAnalyse-OSINT/{__version__} (desktop research tool; respects API terms)"


class PoliteSession:
    def __init__(self, timeout: float = 10.0, min_interval_s: float = 0.35):
        self.timeout = timeout
        self.min_interval_s = min_interval_s
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        retry = Retry(total=2, backoff_factor=0.6, status_forcelist=(500, 502, 503, 504),
                      allowed_methods=("GET", "HEAD"), raise_on_status=False,
                      respect_retry_after_header=False)  # certaines API renvoient Retry-After de plusieurs heures
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
        self._session.mount("https://", adapter)
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def _throttle(self, url: str) -> None:
        host = urlsplit(url).netloc
        with self._lock:
            wait = self._last.get(host, 0.0) + self.min_interval_s - time.monotonic()
            self._last[host] = max(time.monotonic(), self._last.get(host, 0.0) + self.min_interval_s)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, **kwargs) -> requests.Response:
        self._throttle(url)
        kwargs.setdefault("timeout", self.timeout)
        return self._session.get(url, **kwargs)

    def get_json(self, url: str, **kwargs):
        r = self.get(url, **kwargs)
        if r.status_code == 429:
            raise RuntimeError("limite de requêtes atteinte (429), réessayez plus tard")
        r.raise_for_status()
        return r.json()
