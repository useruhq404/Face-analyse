---
name: osint-research
description: >
  Conventions OSINT de FACE ANALYSE : ajouter des sources publiques, vérifier
  pseudonymes/IP, présenter des résultats honnêtes (provenance, fraîcheur,
  homonymes) et respecter le périmètre légal (aucun scraping ni contournement).
  Charger avant de toucher au module OSINT, aux sources ou aux outils IP/Username.
---

# OSINT — FACE ANALYSE

## Où ça vit
- Sources (API officielles) : `face_analyse/osint/sources.py` — une classe par
  source, héritant de `Source`, inscrite dans `all_sources()`.
- Pseudonymes : `osint/usernames.py` (test d'existence, jamais de scraping de contenu).
- IP : `osint/iplookup.py` (ipwho.is / ipinfo.io). Agrégation : `osint/aggregator.py`.
- Liens navigateur (plateformes sans API) : `osint/links.py`.
- Rapport HTML/JSON : `osint/report.py`. Assistant IA : `osint/assistant.py` (API Claude).

## Ajouter une source (recette)
1. Sous-classe de `Source` (`key`, `label`, `category`, `homepage`), méthode
   `search(q: OsintQuery) -> list[OsintResult]` via `self.http.get_json(...)`.
2. Calculer la pertinence avec `name_relevance(q, *textes)` (correspondance de **nom**,
   pas d'identité). Remplir `source`, `url`, `snippet`, `retrieved_at`, `extra`.
3. Inscrire dans `all_sources()`. Débit poli : `PoliteSession` (User-Agent identifié,
   throttle par hôte, retries). Jamais d'IP/e-mail perso dans les requêtes sortantes.
4. Test avec une `FakeHttp` (voir `tests/test_osint.py`), sans réseau.

## Règles intangibles (périmètre légal)
- **API publiques officielles uniquement**, dans le respect de leurs CGU et limites.
- **Jamais** : scraping massif de réseaux sociaux/annuaires, contournement
  d'authentification ou d'anti-robots, bases scrapées, données sensibles,
  identification biométrique de particuliers.
- Plateformes sans API (LinkedIn, Facebook, Instagram, TikTok, X, Pages Jaunes…) :
  **liens de recherche** à ouvrir soi-même, jamais interrogées automatiquement.
- Honnêteté : une correspondance de nom ≠ preuve (homonymes). Afficher provenance,
  URL, date, et un indice de fiabilité. Ne jamais présenter une hypothèse comme un fait.
- Dédoublonnage par URL canonique ; horodatage ; une source en panne ne bloque pas
  les autres (`run_source` capture l'exception et renseigne `SourceStatus`).
