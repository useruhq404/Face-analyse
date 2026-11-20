"""Tests du recon réseau (sans réseau réel : faux client HTTP) + garde-fou ports."""

from __future__ import annotations

import pytest

from face_analyse.osint import netinfo as net


class FakeHttp:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get_json(self, url, **kw):
        self.calls.append((url, kw))
        return self._payload

    def get(self, url, **kw):
        self.calls.append((url, kw))
        payload = self._payload

        class R:
            status_code = 200
            url = "https://exemple.com/"
            headers = {"Server": "nginx", "Strict-Transport-Security": "max-age=1",
                       "Content-Security-Policy": "default-src 'self'"}
        return R()


def test_dns_query_parses_answer():
    http = FakeHttp({"Answer": [{"data": "1.2.3.4"}, {"data": "5.6.7.8"}]})
    assert net.dns_query(http, "exemple.com", "A") == ["1.2.3.4", "5.6.7.8"]


def test_rdap_domain_extracts_fields():
    payload = {"handle": "DOM1", "status": ["active"],
               "events": [{"eventAction": "registration", "eventDate": "2001-01-01"}],
               "nameservers": [{"ldhName": "NS1.EXEMPLE.COM"}],
               "entities": [{"roles": ["registrar"], "vcardArray": [[], [["fn", {}, "text", "Gandi"]]]}]}
    info = net.rdap_domain(FakeHttp(payload), "exemple.com")
    assert info.registrar == "Gandi" and info.statuses == ["active"]
    assert info.events["registration"] == "2001-01-01" and info.nameservers == ["ns1.exemple.com"]


def test_crt_subdomains_dedup():
    payload = [{"name_value": "a.exemple.com\n*.exemple.com"}, {"name_value": "b.exemple.com"}]
    subs = net.crt_subdomains(FakeHttp(payload), "exemple.com")
    assert subs == ["a.exemple.com", "b.exemple.com", "exemple.com"]


def test_http_headers_security_split():
    info = net.http_headers(FakeHttp(None), "exemple.com")
    assert "strict-transport-security" in info.present
    assert "x-frame-options" in info.missing and info.server == "nginx"


def test_scan_ports_refuses_remote_without_authorization():
    with pytest.raises(PermissionError):
        net.scan_ports("example.com", authorized=False)


def test_scan_ports_localhost_allowed():
    res = net.scan_ports("127.0.0.1", ports={9: "discard"}, timeout=0.2)
    assert res.host == "127.0.0.1" and res.scanned == 1
