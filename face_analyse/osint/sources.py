"""Sources publiques interrogées via leurs API officielles.

Chaque source est une classe indépendante ; en ajouter une = écrire une
sous-classe de ``Source`` et l'inscrire dans ``ALL_SOURCES``.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from html import unescape
from urllib.parse import quote

from face_analyse.osint.http import PoliteSession
from face_analyse.osint.models import OsintQuery, OsintResult, normalize_text

_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return " ".join(unescape(_TAG.sub("", text or "")).split())


def name_relevance(query: OsintQuery, *texts: str) -> float:
    """Correspondance du NOM recherché dans le texte (0-1).

    1.0  prénom et nom adjacents (« Thomas Pesquet » ou « PESQUET Thomas »)
    0.7  prénom et nom présents mais séparés
    0.5  nom seul
    0.15 prénom seul

    Mesure la correspondance du nom, pas l'identité : un homonyme obtient 1.0.
    """
    hay = normalize_text(" ".join(texts))
    first = normalize_text(query.first_name).split()
    last = normalize_text(query.last_name).split()
    if not last:
        return 0.0
    f_re = r"\s+".join(map(re.escape, first)) if first else ""
    l_re = r"\s+".join(map(re.escape, last))
    if first and (re.search(rf"\b{f_re}(\s+\w+)?\s+{l_re}\b", hay) or re.search(rf"\b{l_re}\s+{f_re}\b", hay)):
        return 1.0
    last_hit = re.search(rf"\b{l_re}\b", hay) is not None
    first_hit = bool(first) and re.search(rf"\b{f_re}\b", hay) is not None
    if last_hit and first_hit:
        return 0.7
    if last_hit:
        return 0.5
    if first_hit:
        return 0.15
    return 0.0


class Source(ABC):
    key: str = ""
    label: str = ""
    category: str = ""
    homepage: str = ""
    requires_key: str | None = None  # nom du secret nécessaire, le cas échéant

    def __init__(self, http: PoliteSession, secrets: dict[str, str] | None = None):
        self.http = http
        self.secrets = secrets or {}

    @abstractmethod
    def search(self, q: OsintQuery) -> list[OsintResult]:
        ...

    def _result(self, q: OsintQuery, title: str, url: str, snippet: str = "", **extra) -> OsintResult:
        return OsintResult(
            source=self.label, category=self.category, title=title, url=url, snippet=snippet,
            relevance=name_relevance(q, title, snippet), extra={k: str(v) for k, v in extra.items() if v},
        )


# ---------------------------------------------------------------- encyclopédies
class WikipediaSource(Source):
    category = "Encyclopédie"
    homepage = "https://www.wikipedia.org"

    def __init__(self, http, secrets=None, lang: str = "fr"):
        super().__init__(http, secrets)
        self.lang = lang
        self.key = f"wikipedia_{lang}"
        self.label = f"Wikipedia ({lang})"

    def search(self, q):
        data = self.http.get_json(
            f"https://{self.lang}.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": f'"{q.full_name}" {q.extra_keywords}'.strip(),
                    "format": "json", "srlimit": 10, "utf8": 1},
        )
        out = []
        for it in data.get("query", {}).get("search", []):
            title = it.get("title", "")
            url = f"https://{self.lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
            out.append(self._result(q, title, url, strip_html(it.get("snippet", ""))))
        return out


class WikidataSource(Source):
    key, label, category = "wikidata", "Wikidata", "Encyclopédie"
    homepage = "https://www.wikidata.org"

    def search(self, q):
        data = self.http.get_json(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbsearchentities", "search": q.full_name, "language": "fr", "uselang": "fr",
                    "format": "json", "limit": 10, "type": "item"},
        )
        return [
            self._result(q, it.get("label", ""), it.get("concepturi") or f"https://www.wikidata.org/wiki/{it.get('id')}",
                         it.get("description", ""), id=it.get("id", ""))
            for it in data.get("search", [])
        ]


# ---------------------------------------------------------------- entreprises
class EntreprisesSource(Source):
    """API Recherche d'entreprises (DINUM, data.gouv.fr) : dirigeants déclarés."""

    key, label, category = "entreprises", "Annuaire des Entreprises (gouv.fr)", "Entreprises"
    homepage = "https://annuaire-entreprises.data.gouv.fr"

    def search(self, q):
        params = {"q": q.last_name, "nom_personne": q.last_name, "prenoms_personne": q.first_name, "per_page": 20}
        data = self.http.get_json("https://recherche-entreprises.api.gouv.fr/search", params=params)
        out = []
        target_last = normalize_text(q.last_name)
        target_first = normalize_text(q.first_name).split()[:1]
        for ent in data.get("results", []):
            roles = []
            for d in ent.get("dirigeants") or []:
                if d.get("type_dirigeant") != "personne physique":
                    continue
                if normalize_text(d.get("nom", "")) != target_last:
                    continue
                prenoms = normalize_text(d.get("prenoms", "")).split()
                if target_first and target_first[0] not in prenoms:
                    continue
                # Minimisation : la date de naissance publiée par le RNE n'est pas reprise.
                roles.append(f"{d.get('prenoms', '').title()} {d.get('nom', '').title()} — {d.get('qualite') or 'dirigeant'}")
            if not roles:
                continue
            siege = ent.get("siege") or {}
            title = ent.get("nom_complet") or ent.get("nom_raison_sociale") or ent.get("siren", "")
            etat = "active" if ent.get("etat_administratif") == "A" else "fermée"
            snippet = "; ".join(roles) + f" | {siege.get('libelle_commune') or siege.get('commune', '')} | entreprise {etat}"
            r = self._result(q, title, f"https://annuaire-entreprises.data.gouv.fr/entreprise/{ent.get('siren')}",
                             snippet, siren=ent.get("siren", ""), creation=ent.get("date_creation", ""))
            r.relevance = max(r.relevance, 1.0)
            out.append(r)
        return out


class BodaccSource(Source):
    """BODACC (DILA) : annonces légales commerciales publiques."""

    key, label, category = "bodacc", "BODACC (annonces légales)", "Entreprises"
    homepage = "https://www.bodacc.fr"

    def search(self, q):
        data = self.http.get_json(
            "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records",
            params={"where": f'search(listepersonnes, "{q.last_name}") and search(listepersonnes, "{q.first_name}")',
                    "limit": 20, "order_by": "dateparution desc"},
        )
        out = []
        for it in data.get("results", []):
            people_txt = " ".join(_bodacc_people(it.get("listepersonnes")))
            # Seuls les dirigeants / personnes physiques comptent (pas les adresses
            # du type « rue Thomas Pesquet »).
            if name_relevance(q, people_txt) < 1.0:
                continue
            title = f"{it.get('familleavis_lib', 'Annonce')} — {it.get('commercant', '')}"
            snippet = f"{it.get('dateparution', '')} · {it.get('tribunal', '')} · {it.get('ville', '')}"
            url = it.get("url_complete") or f"https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:{it.get('id')}"
            r = self._result(q, title, url, snippet, date=it.get("dateparution", ""))
            r.relevance = 1.0
            out.append(r)
        return out


def _bodacc_people(raw) -> list[str]:
    """Extrait les noms de personnes (dirigeants, personnes physiques) d'une annonce."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except ValueError:
        return []
    persons = data.get("personne", []) if isinstance(data, dict) else []
    if isinstance(persons, dict):
        persons = [persons]
    out = []
    for p in persons:
        if not isinstance(p, dict):
            continue
        if p.get("administration"):
            out.append(str(p["administration"]))
        if p.get("typePersonne") == "pp":
            out.append(f"{p.get('nom', '')} {p.get('prenom', '')}")
            if p.get("nomUsage"):
                out.append(f"{p.get('nomUsage')} {p.get('prenom', '')}")
    return out


# ---------------------------------------------------------------- recherche
class OrcidSource(Source):
    key, label, category = "orcid", "ORCID", "Recherche"
    homepage = "https://orcid.org"

    def search(self, q):
        query = f'given-names:"{q.first_name}" AND family-name:"{q.last_name}"'
        data = self.http.get_json("https://pub.orcid.org/v3.0/expanded-search/", params={"q": query, "rows": 20})
        out = []
        for it in data.get("expanded-result") or []:
            name = f"{it.get('given-names', '')} {it.get('family-names', '')}".strip()
            inst = ", ".join((it.get("institution-name") or [])[:3])
            out.append(self._result(q, name, f"https://orcid.org/{it.get('orcid-id')}", inst, orcid=it.get("orcid-id", "")))
        return out


class HalSource(Source):
    key, label, category = "hal", "HAL (archives ouvertes)", "Recherche"
    homepage = "https://hal.science"

    def search(self, q):
        data = self.http.get_json(
            "https://api.archives-ouvertes.fr/search/",
            params={"q": f'authFullName_t:"{q.full_name}"', "fl": "title_s,uri_s,producedDateY_i,authFullName_s",
                    "rows": 15, "wt": "json", "sort": "producedDateY_i desc"},
        )
        out = []
        for d in data.get("response", {}).get("docs", []):
            title = (d.get("title_s") or [""])[0]
            authors = ", ".join((d.get("authFullName_s") or [])[:6])
            r = self._result(q, title, d.get("uri_s", ""), f"{d.get('producedDateY_i', '')} · {authors}")
            r.relevance = name_relevance(q, authors)
            out.append(r)
        return out


class OpenAlexSource(Source):
    key, label, category = "openalex", "OpenAlex", "Recherche"
    homepage = "https://openalex.org"
    requires_key = "openalex_api_key"

    def search(self, q):
        params = {"search": q.full_name, "per-page": 10}
        key = self.secrets.get("openalex_api_key")
        if key:
            params["api_key"] = key
        data = self.http.get_json("https://api.openalex.org/authors", params=params)
        out = []
        for a in data.get("results", []):
            inst = ", ".join(i.get("display_name", "") for i in (a.get("last_known_institutions") or [])[:2])
            out.append(self._result(q, a.get("display_name", ""), a.get("id", ""),
                                    f"{a.get('works_count', 0)} publications · {inst}"))
        return out


# ---------------------------------------------------------------- code
class GitHubSource(Source):
    key, label, category = "github", "GitHub", "Code"
    homepage = "https://github.com"

    def search(self, q):
        data = self.http.get_json(
            "https://api.github.com/search/users",
            params={"q": f'fullname:"{q.full_name}"', "per_page": 15},
            headers={"Accept": "application/vnd.github+json"},
        )
        out = []
        for it in data.get("items", []):
            r = self._result(q, it.get("login", ""), it.get("html_url", ""),
                             f"Compte GitHub dont le nom affiché correspond à « {q.full_name} »")
            r.relevance = max(r.relevance, 0.9)  # filtré côté GitHub sur le nom complet
            out.append(r)
        return out


def all_sources(http: PoliteSession, secrets: dict[str, str] | None = None) -> list[Source]:
    return [
        WikipediaSource(http, secrets, "fr"),
        WikipediaSource(http, secrets, "en"),
        WikidataSource(http, secrets),
        EntreprisesSource(http, secrets),
        BodaccSource(http, secrets),
        OrcidSource(http, secrets),
        HalSource(http, secrets),
        OpenAlexSource(http, secrets),
        GitHubSource(http, secrets),
    ]
