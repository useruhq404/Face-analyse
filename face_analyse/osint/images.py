"""Recherche d'image INVERSÉE par liens (similarité visuelle, pas biométrie).

L'application n'envoie rien automatiquement : elle prépare les URL des moteurs de
recherche inversée, que l'utilisateur ouvre lui-même et où il dépose son image.
But : retrouver où une image publique apparaît — **jamais** identifier une personne
par son visage contre une base.
"""

from __future__ import annotations

from urllib.parse import quote_plus

NOTICE = ("Recherche de similarité visuelle via des moteurs tiers, à ouvrir vous-même. "
          "Ce n'est pas une identification biométrique : aucun visage n'est comparé à une base.")


def reverse_image_links(image_url: str = "") -> list[tuple[str, str]]:
    """Liens des moteurs de recherche inversée.

    Si ``image_url`` (URL publique d'une image) est fournie, construit aussi les
    recherches directes ; sinon, renvoie les pages des moteurs (dépôt manuel).
    """
    links: list[tuple[str, str]] = []
    url = image_url.strip()
    if url.startswith(("http://", "https://")):
        q = quote_plus(url)
        links += [
            ("Yandex Images (par URL)", f"https://yandex.com/images/search?rpt=imageview&url={q}"),
            ("Google (par URL)", f"https://lens.google.com/uploadbyurl?url={q}"),
            ("Bing (par URL)", f"https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{q}"),
            ("TinEye (par URL)", f"https://www.tineye.com/search?url={q}"),
        ]
    links += [
        ("Google Lens", "https://lens.google.com/"),
        ("Google Images", "https://images.google.com/"),
        ("Bing Visual Search", "https://www.bing.com/visualsearch"),
        ("Yandex Images", "https://yandex.com/images/"),
        ("TinEye", "https://tineye.com/"),
    ]
    return links
