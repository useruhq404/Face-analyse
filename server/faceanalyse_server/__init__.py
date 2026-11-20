"""Serveur FACE ANALYSE — comptes, sessions, journal d'activité, panel admin.

Ce serveur est le « coffre » du projet : l'application de bureau ne fonctionne
que si un compte validé par CE serveur l'autorise. Le propriétaire peut, à
distance, suspendre un compte ou révoquer une session. Toute la journalisation
est **transparente** : l'utilisateur est informé, à la connexion, de ce qui est
enregistré (RGPD, art. 13).
"""

__version__ = "1.0.0"
