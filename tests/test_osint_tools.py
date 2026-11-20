"""Tests des outils OSINT : e-mail (Gravatar mocké), téléphone (hors ligne), image."""

from __future__ import annotations

import json

import pytest

from face_analyse.core.errors import OsintError
from face_analyse.osint import email as E
from face_analyse.osint import phone as P
from face_analyse.osint.images import reverse_image_links


class FakeResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload
        self.headers = {"content-type": "application/json" if payload is not None else "text/plain"}
        self.text = json.dumps(payload) if payload is not None else ""

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeHttp:
    def __init__(self, resp):
        self.resp = resp

    def get(self, url, **kw):
        return self.resp


GRAV = {"entry": [{"profileUrl": "https://gravatar.com/jdoe", "preferredUsername": "jdoe",
                   "displayName": "J Doe", "currentLocation": "Paris",
                   "accounts": [{"shortname": "github", "url": "https://github.com/jdoe"}]}]}


# ------------------------------------------------------------ e-mail
def test_email_invalid():
    with pytest.raises(OsintError):
        E.investigate("pas-un-email", FakeHttp(FakeResp(404)))


def test_email_with_gravatar():
    info = E.investigate("john.doe@gmail.com", FakeHttp(FakeResp(200, GRAV)))
    assert info.valid and info.domain == "gmail.com" and info.provider_type == "grand public"
    assert info.gravatar_found and info.gravatar.username == "jdoe"
    assert ("github", "https://github.com/jdoe") in info.gravatar.accounts
    assert "jdoe" in info.username_candidates and "johndoe" in info.username_candidates
    assert any("haveibeenpwned" in u for _, u in info.links)


def test_email_without_gravatar_custom_domain():
    info = E.investigate("contact@ma-societe.fr", FakeHttp(FakeResp(404)))
    assert info.provider_type == "domaine propre" and not info.gravatar_found
    assert info.username_candidates  # pistes quand même


# ------------------------------------------------------------ téléphone
def test_phone_valid_fr_mobile():
    info = P.investigate("+33612345678")
    assert info.valid and info.country == "FR" and info.line_type == "mobile"
    assert info.e164 == "+33612345678" and "Europe/Paris" in info.timezones
    assert info.carrier  # un opérateur probable


def test_phone_local_with_region():
    info = P.investigate("0612345678", "FR")
    assert info.valid and info.e164 == "+33612345678"


def test_phone_invalid():
    info = P.investigate("12", "FR")
    assert not info.valid and info.note


def test_phone_empty():
    with pytest.raises(OsintError):
        P.investigate("   ")


# ------------------------------------------------------------ image
def test_reverse_image_links():
    base = reverse_image_links()
    assert {"Google Lens", "Yandex Images", "TinEye"} <= {label for label, _ in base}
    with_url = reverse_image_links("https://example.com/a.jpg")
    assert any("par URL" in label for label, _ in with_url)
    assert all(u.startswith("https://") for _, u in with_url)
