"""Tests des générateurs de données de test et du décodeur d'ID Discord."""

from __future__ import annotations

import ipaddress
from datetime import datetime, timezone

import pytest

from face_analyse.osint import generators as g


def test_random_ipv4_public_only():
    ips = g.random_ipv4(30, public_only=True)
    assert len(ips) == 30
    for s in ips:
        a = ipaddress.ip_address(s)
        assert a.is_global and not a.is_private


def test_random_ipv4_in_cidr():
    net = ipaddress.ip_network("192.168.0.0/16")
    for s in g.random_ipv4_in("192.168.0.0/16", 20):
        assert ipaddress.ip_address(s) in net


def test_random_ipv6_and_mac_uuid():
    assert len(g.random_ipv6(5)) == 5
    macs = g.random_mac(10)
    assert all(len(m.split(":")) == 6 for m in macs)
    assert len({*g.random_uuid(20)}) == 20


@pytest.mark.parametrize("country", list(g.IBAN_LENGTHS))
def test_fake_iban_valid_checksum(country):
    for iban in g.fake_iban(country, 5):
        assert g.iban_is_valid(iban)
        assert iban.replace(" ", "").startswith(country)


def test_iban_validator_known_values():
    assert g.iban_is_valid("FR14 2004 1010 0505 0001 3M02 606")
    assert not g.iban_is_valid("FR14 2004 1010 0505 0001 3M02 607")
    assert not g.iban_is_valid("not an iban")


def test_fake_iban_unknown_country():
    with pytest.raises(ValueError):
        g.fake_iban("ZZ", 1)


def test_decode_discord_id_known():
    # Exemple de la doc Discord : 175928847299117063 → 2016-04-30
    info = g.decode_discord_id(175928847299117063)
    assert info.created_at.year == 2016 and info.created_at.month == 4
    assert info.snowflake == 175928847299117063


def test_discord_snowflake_roundtrip():
    dt = datetime(2021, 6, 15, 12, 0, tzinfo=timezone.utc)
    sf = g.snowflake_for(dt)
    back = g.decode_discord_id(sf).created_at
    assert back.year == 2021 and back.month == 6 and back.day == 15


def test_decode_discord_id_invalid():
    with pytest.raises(ValueError):
        g.decode_discord_id("0")
    with pytest.raises(ValueError):
        g.decode_discord_id("-5")
