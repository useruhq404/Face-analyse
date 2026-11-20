"""Module OSINT : recherche par nom/prénom dans des sources publiques autorisées.

Principes :

* Uniquement des **API publiques officielles** interrogées dans le respect de
  leurs conditions (limites de débit, User-Agent identifié).
* Les plateformes sans API publique (LinkedIn, Facebook, Instagram, TikTok,
  Pages Jaunes…) ne sont **jamais scrapées** : l'outil génère des liens de
  recherche que l'utilisateur ouvre lui-même dans son navigateur.
* Aucun lien n'est fait avec le moteur facial : on ne cherche jamais une
  personne à partir de son visage.
* Un résultat signifie « une page publique mentionne ce nom », jamais
  « c'est la même personne » (homonymes).
"""
