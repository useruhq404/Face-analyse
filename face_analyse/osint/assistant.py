"""Assistant IA de recherche (API Claude).

Deux fonctions :

* ``suggest`` : variantes du nom, pseudonymes probables et pistes de recherche ;
* ``summarize`` : synthèse française des résultats déjà collectés.

L'assistant travaille uniquement sur du texte (nom, résultats publics). Il
ne reçoit jamais d'image et n'est jamais relié au moteur facial. La clé API
est saisie par l'utilisateur dans SETTINGS et stockée chiffrée.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from face_analyse.core.errors import OsintError
from face_analyse.osint.models import OsintQuery, OsintReport

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """Tu es l'assistant de recherche OSINT de l'application FACE ANALYSE.
Tu aides un utilisateur à explorer des informations PUBLIQUES à partir d'un nom.
Règles :
- Tu ne fabriques jamais de faits, de profils, d'URL ou de coordonnées. Tu ne travailles qu'à partir de ce qu'on te fournit.
- Une correspondance de nom ne prouve pas l'identité : signale les homonymes probables et les incohérences.
- Tu ne proposes pas de contourner des restrictions d'accès, de deviner des mots de passe, ni de localiser une personne
  à son domicile. Ne mets pas en avant d'adresses ou de téléphones de particuliers.
- Réponds en français, de façon concise et structurée."""

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "name_variants": {"type": "array", "items": {"type": "string"}},
        "usernames": {"type": "array", "items": {"type": "string"}},
        "search_ideas": {"type": "array", "items": {"type": "string"}},
        "caution": {"type": "string"},
    },
    "required": ["name_variants", "usernames", "search_ideas", "caution"],
    "additionalProperties": False,
}


@dataclass
class Suggestions:
    name_variants: list[str]
    usernames: list[str]
    search_ideas: list[str]
    caution: str


class ResearchAssistant:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        if not api_key:
            raise OsintError("Clé API Claude manquante : renseignez-la dans SETTINGS.")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise OsintError("Le paquet « anthropic » n'est pas installé.") from exc
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=120)
        self.model = model

    def _call(self, user_content: str, max_tokens: int, schema: dict | None = None) -> str:
        a = self._anthropic
        output_config: dict = {"effort": "medium"}
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        try:
            resp = self._client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
                output_config=output_config,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except a.AuthenticationError as exc:
            raise OsintError("Clé API Claude invalide.") from exc
        except a.RateLimitError as exc:
            raise OsintError("Limite de requêtes Claude atteinte, réessayez dans un instant.") from exc
        except a.APIStatusError as exc:
            raise OsintError(f"Erreur de l'API Claude ({exc.status_code}).") from exc
        except a.APIConnectionError as exc:
            raise OsintError("Connexion à l'API Claude impossible.") from exc
        if resp.stop_reason == "refusal":
            raise OsintError("L'assistant a refusé cette demande.")
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if not text:
            raise OsintError("Réponse vide de l'assistant.")
        return text

    def suggest(self, q: OsintQuery) -> Suggestions:
        prompt = (
            f"Personne recherchée : {q.full_name}\nVille (facultatif) : {q.city or '-'}\n"
            f"Mots-clés : {q.extra_keywords or '-'}\n\n"
            "Propose : des variantes d'écriture du nom (accents, ordre, prénoms composés, translittérations), "
            "au plus 10 pseudonymes plausibles (lettres, chiffres, . _ - uniquement), et au plus 8 idées de "
            "recherches publiques pertinentes. Ajoute une mise en garde courte sur les homonymes."
        )
        data = json.loads(self._call(prompt, 4000, SUGGEST_SCHEMA))
        return Suggestions(
            name_variants=[str(x) for x in data.get("name_variants", [])][:15],
            usernames=[str(x) for x in data.get("usernames", [])][:10],
            search_ideas=[str(x) for x in data.get("search_ideas", [])][:8],
            caution=str(data.get("caution", "")),
        )

    def summarize(self, rep: OsintReport) -> str:
        items = [
            {"source": r.source, "categorie": r.category, "titre": r.title, "url": r.url,
             "extrait": r.snippet[:300], "correspondance_nom": round(r.relevance, 2)}
            for r in rep.results[:80]
        ]
        prompt = (
            f"Résultats publics collectés pour « {rep.query.full_name} » "
            f"(ville : {rep.query.city or '-'}) :\n{json.dumps(items, ensure_ascii=False)}\n\n"
            "Rédige une synthèse : regroupe les résultats qui semblent concerner une même personne, "
            "signale les homonymes probables, indique ce qui reste à vérifier. Cite les URL. "
            "N'invente rien qui ne figure pas dans les résultats."
        )
        return self._call(prompt, 8000)
