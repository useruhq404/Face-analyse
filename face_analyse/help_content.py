"""Contenu d'aide : à quoi sert chaque module et comment il fonctionne.

Structure exploitée par la page GUIDE et par le bouton « ? » de chaque page.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HelpTopic:
    key: str
    title: str
    purpose: str          # à quoi ça sert
    how: str              # comment ça marche
    steps: list[str]      # comment l'utiliser
    cautions: list[str]   # limites / précautions


TOPICS: list[HelpTopic] = [
    HelpTopic(
        "analysis", "FACE ANALYSIS",
        "Analyser une photo : repérer tous les visages, et dire si l'un d'eux correspond à une "
        "personne enregistrée (avec consentement) dans votre base locale.",
        "Le moteur détecte les visages (modèle YuNet), transforme chaque visage en une « empreinte » "
        "numérique de 128 nombres (modèle SFace), puis compare cette empreinte à celles de votre base. "
        "Si la ressemblance dépasse le seuil, il propose une correspondance ; sinon il affiche UNKNOWN.",
        ["Onglet ANALYSER : importez une photo (ou glissez-la).",
         "Chaque visage est encadré et étiqueté (nom ou UNKNOWN).",
         "Le panneau de droite détaille le score, la qualité et les correspondances possibles.",
         "Onglet COMPARER : chargez deux photos pour mesurer leur ressemblance 1:1."],
        ["Un score n'est pas une preuve d'identité : deux personnes peuvent se ressembler.",
         "Une personne absente de la base reste toujours UNKNOWN."],
    ),
    HelpTopic(
        "camera", "CAMÉRA LIVE",
        "Reconnaître en direct, à la webcam, les personnes enregistrées dans votre base.",
        "La caméra tourne dans un fil dédié : chaque image est analysée, un cadre suit chaque tête, "
        "et la reconnaissance est faite périodiquement puis confirmée par un vote sur plusieurs images "
        "(pour éviter qu'une image isolée nomme quelqu'un par erreur).",
        ["Cliquez ACTIVER LA CAMÉRA et autorisez l'accès.",
         "Un cadre blanc suit chaque visage ; le nom s'affiche si la personne est connue.",
         "CHANGER DE CAMÉRA bascule entre webcam avant / arrière / USB.",
         "ENREGISTRER CE VISAGE ajoute l'image courante comme référence d'une personne consentante."],
        ["Aucune détection de vivacité : une photo tenue devant la caméra serait reconnue. "
         "N'utilisez pas l'outil comme contrôle d'accès."],
    ),
    HelpTopic(
        "database", "FACE DATABASE",
        "Gérer les personnes qui ont accepté d'être reconnues : leurs photos et empreintes.",
        "Chaque personne a un consentement horodaté et plusieurs photos de référence. Photos et "
        "empreintes sont chiffrées sur le disque (AES via Fernet, clé protégée par DPAPI sous Windows).",
        ["AJOUTER UNE PERSONNE (consentement obligatoire).",
         "AJOUTER DES PHOTOS : plusieurs angles/lumières améliorent la fiabilité.",
         "SUPPRIMER TOUTES SES DONNÉES efface définitivement la personne (RGPD)."],
        ["N'enregistrez que des personnes consentantes : les empreintes sont des données biométriques "
         "sensibles (art. 9 RGPD)."],
    ),
    HelpTopic(
        "osint", "OSINT SEARCH",
        "Rechercher des informations publiques à partir d'un nom et d'un prénom.",
        "L'app interroge en parallèle des API publiques officielles (Wikipedia, Wikidata, Annuaire des "
        "Entreprises, BODACC, ORCID, HAL, OpenAlex, GitHub), dédoublonne et classe les résultats. Les "
        "plateformes sans API (réseaux sociaux, Pages Jaunes…) sont proposées en liens à ouvrir vous-même.",
        ["Saisissez prénom + nom (ville et mots-clés affinent).",
         "RECHERCHER lance toutes les sources ; l'onglet RÉSULTATS liste les trouvailles avec leurs URL.",
         "IA · SUGGÉRER / SYNTHÈSE : l'assistant propose des pistes et résume (clé API dans SETTINGS).",
         "EXPORTER LE RAPPORT génère un fichier HTML/JSON horodaté."],
        ["Une correspondance de nom ne prouve pas qu'il s'agit de la même personne (homonymes).",
         "Aucune recherche par visage ; respectez la vie privée et les CGU des sites."],
    ),
    HelpTopic(
        "tools_ip", "IP LOOKUP",
        "Obtenir les informations publiques d'une adresse IP ou d'un domaine.",
        "L'app résout le domaine en IP, fait un DNS inverse, puis interroge des bases publiques "
        "(ipwho.is, ipinfo.io) pour la géolocalisation approximative, l'opérateur (ASN) et des indices "
        "d'hébergement/proxy.",
        ["Saisissez une IP (ex. 1.1.1.1) ou un domaine (ex. exemple.com).",
         "RECHERCHER affiche pays/ville, opérateur, DNS inverse, carte approximative."],
        ["La géolocalisation IP indique la zone de l'opérateur, pas le domicile d'une personne.",
         "Précision variable, surtout sur mobile et VPN."],
    ),
    HelpTopic(
        "tools_username", "USERNAME TRACKER",
        "Vérifier sur quelles plateformes un pseudonyme existe.",
        "Pour chaque plateforme, l'app teste l'existence du profil public (API publique ou code HTTP), "
        "sans récupérer le contenu. Elle n'affiche que « ce compte existe », avec le lien.",
        ["Saisissez un pseudonyme.",
         "PISTER teste ~19 plateformes en parallèle et liste les profils trouvés.",
         "Double-cliquez un résultat pour l'ouvrir dans le navigateur."],
        ["Un même pseudo est souvent utilisé par des personnes différentes : « trouvé » ne prouve "
         "pas que c'est la bonne personne."],
    ),
    HelpTopic(
        "console", "CONSOLE",
        "Un terminal intégré pour apprendre la cyber et manipuler des sources publiques.",
        "Interpréteur de commandes réel : recon réseau par API publiques (DNS-over-HTTPS, RDAP, crt.sh, "
        "en-têtes HTTP, certificat TLS), scan de ports limité à tes propres machines, crypto/encodage hors "
        "ligne (hash, base64, hex, rot13, morse, mots de passe), générateurs de données de test, décodeur "
        "d'ID Discord, et des fiches `learn`.",
        ["Tape `help` pour la liste des commandes, `learn` pour les fiches pédagogiques.",
         "Recon : `dns exemple.com`, `whois exemple.com`, `subdomains exemple.com`, `headers tonsite.com`.",
         "Crypto : `hash sha256 texte`, `b64 enc secret`, `pwgen 24`. Flèches ↑/↓ = historique."],
        ["Ne vise QUE tes propres systèmes ou une cible explicitement autorisée.",
         "Pas de DDoS, bruteforce, scraping ni contournement : c'est illégal et absent de l'outil.",
         "Pour mesurer la charge de tes services, utilise le module STRESS TEST."],
    ),
    HelpTopic(
        "lab", "CYBER LAB",
        "Apprendre la sécurité offensive légalement, avec progression suivie.",
        "Rassemble des plateformes de challenges (TryHackMe, Hack The Box, Root-Me, PortSwigger, picoCTF…), "
        "un guide pour monter un lab isolé (VMs host-only + cibles volontairement vulnérables), des fiches par "
        "thème (recon, web, réseau, privesc, crypto) avec les outils et ressources officiels, et une "
        "méthodologie de pentest en checklist dont la progression est enregistrée en local.",
        ["Ouvre les plateformes/ressources d'un clic (navigateur).",
         "Coche les étapes de la méthodologie au fur et à mesure : c'est sauvegardé.",
         "Monte d'abord ton lab isolé, puis pratique dessus."],
        ["Ne pratique que sur tes machines, un lab isolé, ou avec une autorisation écrite.",
         "Le DoS n'est étudié que côté défense ; viser un tiers est un délit."],
    ),
    HelpTopic(
        "account", "COMPTE & SÉCURITÉ",
        "Comprendre la connexion par compte et ce qui est journalisé.",
        "Si un serveur est configuré, l'app exige une connexion (e-mail, Discord ou Google). "
        "L'administrateur peut voir qui est connecté, depuis quelle machine et quelle IP, suspendre un "
        "compte ou fermer une session à distance. Ce qui est enregistré vous est présenté à la connexion.",
        ["Connectez-vous ou créez un compte (pseudo + avatar).",
         "Sans serveur configuré, l'app fonctionne en mode autonome, sans compte."],
        ["La journalisation est transparente (RGPD) : vous êtes informé avant de créer un compte.",
         "Le contenu de vos images et recherches n'est PAS envoyé au serveur ; seules les actions "
         "(module ouvert, recherche lancée) et les infos de connexion le sont."],
    ),
    HelpTopic(
        "settings", "SETTINGS",
        "Régler le moteur, la caméra, l'OSINT, le compte et protéger vos données.",
        "Le seuil de décision affiche en direct les taux d'erreur mesurés sur LFW. Les clés API et le "
        "jeton de session sont chiffrés localement. Vous pouvez tout effacer.",
        ["Réglez le seuil selon votre tolérance aux faux positifs.",
         "Renseignez l'URL du serveur pour activer les comptes, et vos clés API.",
         "Effacez la base biométrique ou les clés à tout moment."],
        ["Changer de modèle d'empreintes impose de recalibrer le seuil (benchmark)."],
    ),
]

BY_KEY = {t.key: t for t in TOPICS}


def topic_for_page(page_key: str) -> HelpTopic | None:
    return BY_KEY.get(page_key)
