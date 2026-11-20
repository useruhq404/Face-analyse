"""Liens de recherche pour les plateformes sans API publique.

Ces plateformes (LinkedIn, Facebook, Instagram, TikTok, X, Pages Jaunes…)
interdisent la collecte automatisée. L'application ne les interroge donc
PAS : elle prépare des URL de recherche que l'utilisateur ouvre lui-même
dans son navigateur, avec son propre compte, dans le respect des règles
de chaque site.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from face_analyse.osint.models import OsintQuery, SearchLink


def build_links(q: OsintQuery) -> list[SearchLink]:
    name = q.full_name
    exact = f'"{name}"'
    qp = quote_plus
    city = q.city.strip()
    ctx = f" {city}" if city else ""
    g = "https://www.google.com/search?q="

    links = [
        # Réseaux sociaux
        SearchLink("LinkedIn", "Réseaux sociaux", f"https://www.linkedin.com/search/results/people/?keywords={qp(name)}", "connexion LinkedIn requise"),
        SearchLink("LinkedIn (via Google)", "Réseaux sociaux", g + qp(f"site:linkedin.com/in {exact}{ctx}")),
        SearchLink("Facebook", "Réseaux sociaux", f"https://www.facebook.com/search/people/?q={qp(name)}", "connexion requise"),
        SearchLink("Instagram (via Google)", "Réseaux sociaux", g + qp(f"site:instagram.com {exact}")),
        SearchLink("TikTok", "Réseaux sociaux", f"https://www.tiktok.com/search/user?q={qp(name)}"),
        SearchLink("X / Twitter", "Réseaux sociaux", f"https://x.com/search?q={qp(name)}&f=user", "connexion requise"),
        SearchLink("YouTube (chaînes)", "Réseaux sociaux", f"https://www.youtube.com/results?search_query={qp(name)}&sp=EgIQAg%253D%253D"),
        SearchLink("Snapchat (via Google)", "Réseaux sociaux", g + qp(f"site:snapchat.com {exact}")),
        SearchLink("Pinterest", "Réseaux sociaux", f"https://www.pinterest.com/search/users/?q={qp(name)}"),
        SearchLink("Reddit", "Réseaux sociaux", f"https://www.reddit.com/search/?q={qp(name)}&type=user"),
        SearchLink("Threads (via Google)", "Réseaux sociaux", g + qp(f"site:threads.net {exact}")),
        # Annuaires
        SearchLink("Pages Blanches", "Annuaires", f"https://www.pagesjaunes.fr/pagesblanches/recherche?quoiqui={qp(name)}&ou={qp(city)}",
                   "annuaire des particuliers (listes publiées volontairement)"),
        SearchLink("Pages Jaunes (pros)", "Annuaires", f"https://www.pagesjaunes.fr/annuaire/chercherlespros?quoiqui={qp(name)}&ou={qp(city)}"),
        SearchLink("Societe.com", "Entreprises", f"https://www.societe.com/cgi-bin/search?champs={qp(name)}"),
        SearchLink("Pappers", "Entreprises", f"https://www.pappers.fr/recherche?q={qp(name)}"),
        SearchLink("Annuaire des Entreprises", "Entreprises", f"https://annuaire-entreprises.data.gouv.fr/rechercher?terme={qp(name)}"),
        # Moteurs
        SearchLink("Google", "Moteurs", g + qp(f"{exact}{ctx} {q.extra_keywords}".strip())),
        SearchLink("Bing", "Moteurs", "https://www.bing.com/search?q=" + qp(f"{exact}{ctx}")),
        SearchLink("DuckDuckGo", "Moteurs", "https://duckduckgo.com/?q=" + qp(f"{exact}{ctx}")),
        SearchLink("Google Actualités", "Moteurs", "https://news.google.com/search?q=" + qp(exact)),
        SearchLink("CV / documents publics", "Moteurs", g + qp(f"{exact} (CV OR curriculum) filetype:pdf")),
        SearchLink("Google Scholar", "Recherche", "https://scholar.google.com/scholar?q=" + qp(f'author:"{name}"')),
    ]
    for u in q.usernames:
        links.append(SearchLink(f"Pseudo « {u} » (Google)", "Pseudonymes", g + qp(f'"{u}"')))
    return links
