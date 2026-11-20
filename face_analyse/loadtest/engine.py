"""Moteur de test de charge HTTP (asyncio + httpx), orienté MESURE.

Envoie des requêtes concurrentes vers une cible et renvoie des métriques réelles
(débit, latence p50/p90/p99, codes, erreurs). Outil de performance, pas une arme :
l'appelant (l'interface) exige une autorisation pour toute cible non locale, et
les paramètres sont bornés.
"""

from __future__ import annotations

import asyncio
import ipaddress
import statistics
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

MAX_CONCURRENCY = 500
MAX_DURATION = 120.0
MAX_REQUESTS = 200_000


@dataclass
class LoadConfig:
    url: str
    concurrency: int = 20
    duration: float = 10.0
    requests: int | None = None
    ramp: float = 0.0
    rps: int = 0
    timeout: float = 10.0
    method: str = "GET"
    body: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    verify_tls: bool = True

    def clamp(self) -> None:
        self.concurrency = max(1, min(self.concurrency, MAX_CONCURRENCY))
        self.duration = max(1.0, min(self.duration, MAX_DURATION))
        if self.requests is not None:
            self.requests = max(1, min(self.requests, MAX_REQUESTS))


@dataclass
class Results:
    latencies: list[float] = field(default_factory=list)
    status: dict[int, int] = field(default_factory=dict)
    errors: dict[str, int] = field(default_factory=dict)
    duration: float = 0.0

    @property
    def ok(self) -> int:
        return sum(self.status.values())

    @property
    def failed(self) -> int:
        return sum(self.errors.values())

    @property
    def total(self) -> int:
        return self.ok + self.failed

    @property
    def rps(self) -> float:
        return self.total / self.duration if self.duration else 0.0

    def pct(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        k = min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))
        return s[k]

    @property
    def mean_latency(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0.0

    def latency_histogram(self, bins: int = 12) -> list[tuple[str, int]]:
        from face_analyse.dataset.analysis import histogram

        return histogram(self.latencies, bins=bins)


def is_local_target(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", ""):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return host.endswith(".local")


async def _worker(client, cfg, res, stop_at, counter, lock, rate_sem):
    body = cfg.body.encode() if cfg.body else None
    while True:
        if stop_at is not None and time.perf_counter() >= stop_at:
            return
        if cfg.requests is not None:
            async with lock:
                if counter[0] >= cfg.requests:
                    return
                counter[0] += 1
        if rate_sem is not None:
            await rate_sem.acquire()
        t0 = time.perf_counter()
        try:
            r = await client.request(cfg.method, cfg.url, content=body, headers=cfg.headers or None)
            res.latencies.append((time.perf_counter() - t0) * 1000)
            res.status[r.status_code] = res.status.get(r.status_code, 0) + 1
        except httpx.TimeoutException:
            res.errors["timeout"] = res.errors.get("timeout", 0) + 1
        except httpx.HTTPError as exc:
            name = type(exc).__name__
            res.errors[name] = res.errors.get(name, 0) + 1


async def _rate_filler(rate_sem, rps, stop_evt):
    interval = 1.0 / rps
    while not stop_evt.is_set():
        try:
            rate_sem.release()
        except ValueError:
            pass
        await asyncio.sleep(interval)


async def run_async(cfg: LoadConfig, transport=None, progress=None) -> Results:
    cfg.clamp()
    res = Results()
    start = time.perf_counter()
    stop_at = (start + cfg.duration) if cfg.requests is None else None
    counter = [0]
    lock = asyncio.Lock()
    rate_sem = asyncio.Semaphore(0) if cfg.rps else None
    stop_evt = asyncio.Event()
    filler = asyncio.create_task(_rate_filler(rate_sem, cfg.rps, stop_evt)) if rate_sem else None

    limits = httpx.Limits(max_connections=cfg.concurrency + 10, max_keepalive_connections=cfg.concurrency)
    client_kw = {"timeout": cfg.timeout, "limits": limits, "verify": cfg.verify_tls}
    if transport is not None:
        client_kw["transport"] = transport
    async with httpx.AsyncClient(**client_kw) as client:
        tasks = []
        for _ in range(cfg.concurrency):
            if cfg.ramp:
                await asyncio.sleep(cfg.ramp / cfg.concurrency)
            tasks.append(asyncio.create_task(_worker(client, cfg, res, stop_at, counter, lock, rate_sem)))
        if progress is not None:
            await _report_progress(res, cfg, start, stop_at, tasks, progress)
        await asyncio.gather(*tasks)
    if filler:
        stop_evt.set()
        filler.cancel()
    res.duration = time.perf_counter() - start
    return res


async def _report_progress(res, cfg, start, stop_at, tasks, progress):
    """Émet l'avancement pendant que les workers tournent (sans les bloquer)."""
    while not all(t.done() for t in tasks):
        elapsed = time.perf_counter() - start
        if stop_at is not None:
            frac = min(1.0, elapsed / max(cfg.duration, 1e-9))
        else:
            frac = min(1.0, res.total / max(cfg.requests or 1, 1))
        progress(res.total, int(frac * 100))
        await asyncio.sleep(0.25)


def run(cfg: LoadConfig, transport=None, progress=None) -> Results:
    """Version synchrone (à appeler dans un thread de travail)."""
    return asyncio.run(run_async(cfg, transport=transport, progress=progress))
