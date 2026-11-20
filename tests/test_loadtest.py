"""Tests du moteur de test de charge (httpx MockTransport, sans réseau réel)."""

from __future__ import annotations

import httpx
import pytest

from face_analyse.loadtest.engine import (LoadConfig, Results, combined_latencies, is_local_target, run, run_many)


def _ok_transport(status=200):
    return httpx.MockTransport(lambda req: httpx.Response(status, text="ok"))


def test_is_local_target():
    assert is_local_target("http://127.0.0.1:8090/")
    assert is_local_target("http://localhost/")
    assert is_local_target("http://192.168.1.10/")
    assert not is_local_target("https://example.com/")


def test_config_clamp():
    c = LoadConfig(url="x", concurrency=99999, duration=9999, requests=10**9)
    c.clamp()
    assert c.concurrency == 500 and c.duration == 120.0 and c.requests == 200000


def test_run_by_requests_counts_exactly():
    cfg = LoadConfig(url="http://127.0.0.1/", concurrency=10, requests=200)
    res = run(cfg, transport=_ok_transport())
    assert res.total == 200 and res.ok == 200 and res.status.get(200) == 200
    assert res.failed == 0 and res.rps > 0 and res.latencies


def test_run_records_errors_and_status():
    res = run(LoadConfig(url="http://127.0.0.1/", concurrency=5, requests=50), transport=_ok_transport(503))
    assert res.status.get(503) == 50
    # transport qui lève → erreurs comptées, pas de plantage
    def boom(req):
        raise httpx.ConnectError("refused")
    res2 = run(LoadConfig(url="http://127.0.0.1/", concurrency=5, requests=30),
               transport=httpx.MockTransport(boom))
    assert res2.failed == 30 and res2.ok == 0


def test_run_many_targets_simultaneously():
    cfgs = [LoadConfig(url=f"http://127.0.0.1/{i}", concurrency=8, requests=120) for i in range(3)]
    pairs = run_many(cfgs, transport=_ok_transport())
    assert len(pairs) == 3
    assert all(res.total == 120 and res.ok == 120 for _cfg, res in pairs)
    agg = combined_latencies(pairs)
    assert agg.total == 360 and agg.status.get(200) == 360
    assert len(agg.latencies) == 360


def test_percentiles_and_histogram():
    res = Results(latencies=[float(i) for i in range(1, 101)], duration=1.0)
    assert res.pct(50) == pytest.approx(50, abs=1)
    assert res.pct(99) == pytest.approx(99, abs=1)
    assert res.total == 0  # pas de status enregistré ici
    hist = res.latency_histogram(10)
    assert sum(n for _, n in hist) == 100 and len(hist) == 10
