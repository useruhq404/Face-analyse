"""Testeur de charge (load testing) — mesure les performances d'un service.

Outil d'APPRENTISSAGE et de mesure, pas une arme. Il envoie des requêtes HTTP
concurrentes vers une cible **que tu possèdes ou que tu es autorisé à tester**
(ta VM, ton serveur de test local) et rapporte des métriques réelles :
débit (req/s), latence (p50/p90/p99), codes de réponse, erreurs.

    # 1) dans un terminal : lance ta cible d'entraînement
    python target_server.py --work-ms 3

    # 2) dans un autre : teste-la (il faut confirmer l'autorisation)
    python loadtest.py http://127.0.0.1:8090 --concurrency 50 --duration 10 --authorized

Paramètres utiles :
    --concurrency N   nombre de clients simultanés (défaut 20)
    --duration S      durée en secondes (défaut 10)   OU   --requests N
    --ramp S          montée en charge progressive sur S secondes
    --rps R           plafond de débit total (0 = aucun)
    --timeout S       délai max par requête (défaut 10)
    --method / --body / --header

Éthique & légalité : ne vise que TES systèmes (ou avec autorisation écrite).
Envoyer du trafic pour saturer/mettre hors service un système tiers est un
déni de service — illégal (France : art. 323-2, jusqu'à 5 ans et 150 000 €).
Cet outil est volontairement orienté MESURE (il s'arrête, rapporte, et respecte
un plafond de débit si tu en mets un).
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx


@dataclass
class Results:
    latencies: list[float] = field(default_factory=list)
    status: dict[int, int] = field(default_factory=dict)
    errors: dict[str, int] = field(default_factory=dict)
    started: float = 0.0
    ended: float = 0.0

    def record_ok(self, code: int, latency: float):
        self.latencies.append(latency)
        self.status[code] = self.status.get(code, 0) + 1

    def record_err(self, name: str):
        self.errors[name] = self.errors.get(name, 0) + 1


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))
    return s[k]


async def _worker(client, url, method, body, headers, res, stop_at, max_requests, counter, rate_sem):
    while True:
        if stop_at and time.perf_counter() >= stop_at:
            return
        if max_requests is not None:
            idx = counter[0]
            if idx >= max_requests:
                return
            counter[0] += 1
        if rate_sem is not None:
            await rate_sem.acquire()
        t0 = time.perf_counter()
        try:
            r = await client.request(method, url, content=body, headers=headers)
            res.record_ok(r.status_code, (time.perf_counter() - t0) * 1000)
        except httpx.TimeoutException:
            res.record_err("timeout")
        except httpx.HTTPError as exc:
            res.record_err(type(exc).__name__)


async def _rate_filler(rate_sem, rps, stop_evt):
    """Libère ``rps`` jetons par seconde (plafond de débit global)."""
    interval = 1.0 / rps
    while not stop_evt.is_set():
        try:
            rate_sem.release()
        except ValueError:
            pass
        await asyncio.sleep(interval)


async def run(args) -> Results:
    headers = {}
    for h in args.header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()
    res = Results(started=time.perf_counter())
    limits = httpx.Limits(max_connections=args.concurrency + 10, max_keepalive_connections=args.concurrency)
    stop_at = (res.started + args.duration) if not args.requests else None
    max_requests = args.requests
    counter = [0]
    rate_sem = asyncio.Semaphore(0) if args.rps else None
    stop_evt = asyncio.Event()
    filler = asyncio.create_task(_rate_filler(rate_sem, args.rps, stop_evt)) if rate_sem else None

    async with httpx.AsyncClient(timeout=args.timeout, limits=limits, verify=not args.insecure) as client:
        workers = []
        for i in range(args.concurrency):
            if args.ramp:
                await asyncio.sleep(args.ramp / args.concurrency)
            workers.append(asyncio.create_task(
                _worker(client, args.url, args.method, args.body.encode() if args.body else None,
                        headers, res, stop_at, max_requests, counter, rate_sem)))
        await asyncio.gather(*workers)
    if filler:
        stop_evt.set()
        filler.cancel()
    res.ended = time.perf_counter()
    return res


def report(args, res: Results):
    dur = max(res.ended - res.started, 1e-9)
    ok = sum(res.status.values())
    err = sum(res.errors.values())
    total = ok + err
    lat = res.latencies
    print("\n" + "=" * 54)
    print(f"  CIBLE        {args.url}")
    print(f"  Durée        {dur:.1f} s   ·   concurrence {args.concurrency}")
    print(f"  Requêtes     {total}   (ok {ok}, erreurs {err})")
    print(f"  Débit        {total / dur:,.1f} req/s")
    if lat:
        print(f"  Latence ms   moy {statistics.mean(lat):.1f} · p50 {_pct(lat,50):.1f} · "
              f"p90 {_pct(lat,90):.1f} · p99 {_pct(lat,99):.1f} · max {max(lat):.1f}")
    if res.status:
        print("  Codes        " + "  ".join(f"{c}:{n}" for c, n in sorted(res.status.items())))
    if res.errors:
        print("  Erreurs      " + "  ".join(f"{k}:{v}" for k, v in res.errors.items()))
    print("=" * 54)
    if err and err / max(total, 1) > 0.05:
        print("  ⚠ Beaucoup d'erreurs : la cible sature, ralentit ou limite le débit.")
    print("  Note : outil de mesure. Ne vise que des systèmes qui t'appartiennent\n"
          "  ou que tu es autorisé à tester.\n")


def main():
    ap = argparse.ArgumentParser(description="Testeur de charge HTTP (mesure de performance).")
    ap.add_argument("url")
    ap.add_argument("--concurrency", type=int, default=20)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--requests", type=int, default=None, help="nombre total de requêtes (prioritaire sur --duration)")
    ap.add_argument("--ramp", type=float, default=0.0, help="montée en charge sur N secondes")
    ap.add_argument("--rps", type=int, default=0, help="plafond de débit global (0 = aucun)")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--method", default="GET")
    ap.add_argument("--body", default="")
    ap.add_argument("--header", action="append")
    ap.add_argument("--insecure", action="store_true", help="ne pas vérifier le certificat TLS (labs seulement)")
    ap.add_argument("--authorized", action="store_true",
                    help="confirme que tu possèdes la cible ou es autorisé à la tester")
    args = ap.parse_args()

    host = (urlparse(args.url).hostname or "").lower()
    is_local = host in ("127.0.0.1", "localhost", "::1") or host.startswith(("10.", "192.168.", "172."))
    if not args.authorized and not is_local:
        print("Refus : cible non locale. Ajoute --authorized UNIQUEMENT si ce système t'appartient\n"
              "ou si tu as une autorisation écrite de test. Viser un tiers = déni de service (illégal).",
              file=sys.stderr)
        sys.exit(2)

    print(f"Load-test → {args.url}  (c={args.concurrency}, "
          f"{'n=' + str(args.requests) if args.requests else 'durée=' + str(args.duration) + 's'}"
          f"{', plafond ' + str(args.rps) + ' req/s' if args.rps else ''})")
    res = asyncio.run(run(args))
    report(args, res)


if __name__ == "__main__":
    main()
