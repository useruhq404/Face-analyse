import json
from urllib.parse import unquote_plus

import pytest

from face_analyse.core.errors import OsintError
from face_analyse.osint.aggregator import OsintEngine, deduplicate
from face_analyse.osint.assistant import ResearchAssistant
from face_analyse.osint.links import build_links
from face_analyse.osint.models import OsintQuery, OsintResult, canonical_url, normalize_text
from face_analyse.osint.report import render_html, save_report
from face_analyse.osint.sources import BodaccSource, EntreprisesSource, Source, WikipediaSource, name_relevance
from face_analyse.osint.usernames import Platform, Presence, candidate_usernames, check_one

Q = OsintQuery("Thomas", "Pesquet")


class FakeHttp:
    def __init__(self, payload=None, status=200, text=""):
        self.payload, self.status, self.text = payload, status, text
        self.calls = []

    def get_json(self, url, **kw):
        self.calls.append((url, kw))
        return self.payload

    def get(self, url, **kw):
        self.calls.append((url, kw))
        payload, status, text = self.payload, self.status, self.text

        class R:
            status_code = status

            def json(self_inner):
                return payload

        r = R()
        r.text = text
        return r


def test_normalize_and_relevance():
    assert normalize_text("  Éloïse  JEAN-Baptiste ") == "eloise jean baptiste"
    assert name_relevance(Q, "Thomas Pesquet est astronaute") == 1.0
    assert name_relevance(Q, "PESQUET Thomas, gérant") == 1.0
    assert name_relevance(Q, "Thomas Gautier Pesquet") == 1.0
    assert name_relevance(Q, "Thomas Dupont et Marie Pesquet") == 0.7
    assert name_relevance(Q, "famille Pesquet") == 0.5
    assert name_relevance(Q, "rien à voir") == 0.0


def test_query_validation():
    with pytest.raises(OsintError):
        OsintQuery("", "X").validate()


def test_canonical_url_and_dedup():
    assert canonical_url("http://www.Example.com/a/") == canonical_url("https://example.com/a")
    a = OsintResult("S1", "C", "t", "https://example.com/p", relevance=0.5)
    b = OsintResult("S2", "C", "t", "http://www.example.com/p/", relevance=0.9)
    c = OsintResult("S3", "C", "t", "https://example.com/other", relevance=0.1)
    out, removed = deduplicate([a, b, c])
    assert removed == 1 and len(out) == 2
    kept = next(r for r in out if r.key == a.key)
    assert kept.source == "S2" and kept.duplicates == ["S1"]


def test_links_are_search_urls_only():
    links = build_links(OsintQuery("Jean", "Dupont", city="Lyon", usernames=("jdupont",)))
    platforms = {link.platform for link in links}
    assert {"LinkedIn", "Facebook", "TikTok", "Pages Blanches", "Pages Jaunes (pros)", "Google"} <= platforms
    for link in links:
        assert link.url.startswith("https://")
        assert "Dupont" in unquote_plus(link.url) or "jdupont" in link.url
    pb = next(link for link in links if link.platform == "Pages Blanches")
    assert "ou=Lyon" in pb.url


def test_candidate_usernames():
    c = candidate_usernames("Élodie", "De La Tour")
    assert "elodiedelatour" in c and "elodie.delatour" in c and "edelatour" in c
    assert candidate_usernames("", "X") == []


@pytest.mark.parametrize("status,payload,text,mode,marker,expected", [
    (200, {"login": "x"}, "", "status", "", Presence.FOUND),
    (404, None, "", "status", "", Presence.ABSENT),
    (429, None, "", "status", "", Presence.UNKNOWN),
    (200, [], "", "json_nonempty", "", Presence.ABSENT),
    (200, [{"id": 1}], "", "json_nonempty", "", Presence.FOUND),
    (200, None, "...not found...", "text_absent", "not found", Presence.ABSENT),
])
def test_username_check_modes(status, payload, text, mode, marker, expected):
    p = Platform("P", "https://api.example/{u}", "https://example/{u}", mode, marker)
    hit = check_one(FakeHttp(payload, status, text), p, "jdoe")
    assert hit.presence == expected and hit.url == "https://example/jdoe"


def test_entreprises_source_filters_on_director_name():
    payload = {"results": [
        {"siren": "1", "nom_complet": "A", "etat_administratif": "A", "siege": {"libelle_commune": "PARIS"},
         "dirigeants": [{"nom": "PESQUET", "prenoms": "THOMAS GAUTIER", "qualite": "Président",
                         "type_dirigeant": "personne physique", "date_de_naissance": "1978-02"}]},
        {"siren": "2", "nom_complet": "B", "siege": {},
         "dirigeants": [{"nom": "PESQUET", "prenoms": "MARIE", "type_dirigeant": "personne physique"}]},
    ]}
    res = EntreprisesSource(FakeHttp(payload)).search(Q)
    assert [r.title for r in res] == ["A"]
    assert "1978" not in res[0].snippet  # minimisation : pas de date de naissance


def test_bodacc_ignores_street_names():
    street = {"personne": {"typePersonne": "pm", "denomination": "X",
                           "adresseSiegeSocial": {"nomVoie": "Thomas Pesquet"}}}
    director = {"personne": {"typePersonne": "pm", "denomination": "NOVESPACE",
                             "administration": "Directeur général : PESQUET Thomas Gautier"}}
    payload = {"results": [
        {"id": "1", "commercant": "X", "listepersonnes": json.dumps(street)},
        {"id": "2", "commercant": "NOVESPACE", "familleavis_lib": "Modifications", "listepersonnes": json.dumps(director)},
    ]}
    res = BodaccSource(FakeHttp(payload)).search(Q)
    assert len(res) == 1 and "NOVESPACE" in res[0].title


def test_wikipedia_source_parses():
    payload = {"query": {"search": [{"title": "Thomas Pesquet", "snippet": "<span>astronaute</span> français"}]}}
    res = WikipediaSource(FakeHttp(payload), lang="fr").search(Q)
    assert res[0].url == "https://fr.wikipedia.org/wiki/Thomas_Pesquet"
    assert res[0].snippet == "astronaute français" and res[0].relevance == 1.0


class Boom(Source):
    key, label, category = "boom", "Boom", "Test"

    def search(self, q):
        raise RuntimeError("panne")


class Ok(Source):
    key, label, category = "ok", "Ok", "Test"

    def search(self, q):
        return [self._result(q, "Thomas Pesquet", "https://ok.example/1"),
                self._result(q, "Sans rapport", "https://ok.example/2")]


def test_aggregator_survives_failing_source():
    eng = OsintEngine(sources=[Boom(None), Ok(None)])
    rep = eng.run(Q, check_handles=False)
    assert [r.url for r in rep.results] == ["https://ok.example/1"]  # résultat hors-sujet filtré
    st = {s.source: s for s in rep.statuses}
    assert not st["Boom"].ok and "panne" in st["Boom"].error and st["Ok"].ok
    assert rep.links


def test_report_html_escapes_and_saves(tmp_path):
    eng = OsintEngine(sources=[Ok(None)])
    rep = eng.run(OsintQuery("Thomas", "Pesquet<script>"), check_handles=False)
    html = render_html(rep)
    assert "<script>" not in html and "&lt;script&gt;" in html
    h, j = save_report(rep, tmp_path)
    assert h.exists() and json.loads(j.read_text(encoding="utf-8"))["query"]["first_name"] == "Thomas"


def test_assistant_requires_key():
    with pytest.raises(OsintError):
        ResearchAssistant("")
