"""Bibliothèque pédagogique de la console — notions de cybersécurité.

Texte éducatif (recon, web, crypto, mots de passe, défense). On explique comment
les choses fonctionnent et comment s'en protéger — pas de recette d'attaque clé
en main. Chaque fiche renvoie à une commande réelle de la console à essayer sur
TES propres cibles.
"""

from __future__ import annotations

LESSONS: dict[str, str] = {
    "osint": (
        "OSINT — renseignement en sources ouvertes\n"
        "Collecter ce qui est PUBLIC et légal : API officielles, registres, moteurs.\n"
        "Règle d'or : une correspondance de nom n'est pas une preuve (homonymes).\n"
        "À essayer : `ip 1.1.1.1`, `dns github.com`, `whois github.com`.\n"
        "Limites : jamais de scraping, de contournement d'anti-robots, ni d'identification\n"
        "biométrique de personnes non consentantes."
    ),
    "recon": (
        "Reconnaissance réseau\n"
        "Cartographier une infrastructure QUE TU POSSÈDES avant de la durcir :\n"
        " • DNS   → quels services exposés ?  `dns exemple.com MX`\n"
        " • RDAP  → qui gère le domaine, dates d'expiration  `whois exemple.com`\n"
        " • crt.sh→ sous-domaines oubliés via les certificats  `subdomains exemple.com`\n"
        " • ports → services ouverts  `ports 127.0.0.1`\n"
        "Défense : réduire la surface exposée, fermer les ports inutiles, surveiller les\n"
        "certificats émis sur ton domaine."
    ),
    "web": (
        "Sécurité web — en-têtes HTTP\n"
        "Des en-têtes de réponse protègent les visiteurs :\n"
        " • Strict-Transport-Security : force HTTPS\n"
        " • Content-Security-Policy    : limite les scripts (anti-XSS)\n"
        " • X-Frame-Options            : anti-clickjacking\n"
        " • X-Content-Type-Options     : empêche le MIME sniffing\n"
        "À essayer : `headers tonsite.com` → liste présents/absents.\n"
        "Top 10 OWASP : injection, auth cassée, XSS, contrôle d'accès… à réviser."
    ),
    "crypto": (
        "Hachage vs chiffrement\n"
        "Hash (MD5/SHA) = empreinte À SENS UNIQUE : sert à vérifier l'intégrité, PAS à\n"
        "chiffrer. On ne « déchiffre » pas un hash ; on peut seulement comparer.\n"
        "MD5 et SHA-1 sont cassés (collisions) → pour un mot de passe utiliser bcrypt,\n"
        "scrypt ou Argon2 (lents + sel).\n"
        "À essayer : `hash sha256 bonjour`, `hashid 5d41402abc4b2a76b9719d911017c592`,\n"
        "`b64 enc secret`, `rot13 message`."
    ),
    "passwords": (
        "Mots de passe & entropie\n"
        "La force vient de l'ENTROPIE (bits) = longueur × log2(taille de l'alphabet).\n"
        "Une phrase longue bat un mot court compliqué. Jamais de réutilisation ; un\n"
        "gestionnaire + 2FA. On ne stocke jamais un mot de passe en clair ni en MD5.\n"
        "À essayer : `pwgen 24` puis observe l'entropie affichée."
    ),
    "dos": (
        "Déni de service — côté DÉFENSE (le seul côté légal)\n"
        "Un DDoS sature une cible de trafic. LANCER une telle attaque est un délit\n"
        "(France : art. 323-2, jusqu'à 5 ans). Cette application n'en fournit pas.\n"
        "Ce que tu peux faire légalement : mesurer la tenue en charge de TES propres\n"
        "services (module STRESS TEST) et apprendre à te protéger : CDN/anti-DDoS,\n"
        "limitation de débit (rate limiting), autoscaling, filtrage, pages de cache.\n"
        "Teste ta résistance sur localhost : `ports 127.0.0.1` puis l'onglet STRESS TEST."
    ),
    "ethics": (
        "Cadre légal & éthique\n"
        "Ne teste que ce qui t'appartient ou ce pour quoi tu as une AUTORISATION ÉCRITE.\n"
        "Intrusion, DDoS, scraping de données perso, usurpation : pénalement réprimés.\n"
        "La cyber défensive (blue team), le CTF et le pentest AUTORISÉ sont la voie pour\n"
        "apprendre sans rien risquer. Reste du bon côté — c'est aussi plus employable."
    ),
}

ORDER = ["osint", "recon", "web", "crypto", "passwords", "dos", "ethics"]


def lesson(topic: str) -> str:
    topic = topic.strip().lower()
    if not topic:
        lines = ["Fiches disponibles (ex. `learn recon`) :"]
        lines += [f"  • {t}" for t in ORDER]
        return "\n".join(lines)
    return LESSONS.get(topic, f"Fiche inconnue : {topic}. Essaie : {', '.join(ORDER)}")
