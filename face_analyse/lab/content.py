"""Contenu du module CYBER LAB.

Apprendre la sécurité offensive **légalement** : plateformes de challenges faites
pour ça, montage d'un lab isolé chez soi, et méthodologie de pentest. Aucune
instruction d'attaque contre un tiers : tout se pratique sur des cibles conçues
pour l'exercice (CTF, VMs volontairement vulnérables, machines qu'on possède).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Platform:
    name: str
    url: str
    level: str          # Débutant | Intermédiaire | Avancé | Tous niveaux
    desc: str


@dataclass(frozen=True)
class Theme:
    key: str
    title: str
    summary: str
    skills: list[str] = field(default_factory=list)
    resources: list[tuple[str, str]] = field(default_factory=list)  # (libellé, url)


@dataclass(frozen=True)
class Phase:
    title: str
    items: list[tuple[str, str]] = field(default_factory=list)      # (id, intitulé)


#: Plateformes légales (cibles faites pour la pratique).
PLATFORMS: list[Platform] = [
    Platform("TryHackMe", "https://tryhackme.com", "Débutant",
             "Parcours guidés, machines par thème. Le meilleur point de départ."),
    Platform("Hack The Box", "https://www.hackthebox.com", "Intermédiaire",
             "Machines et parcours (Academy). Plus brut, très complet."),
    Platform("Root-Me", "https://www.root-me.org", "Tous niveaux",
             "Challenges FR par catégorie (web, crackme, réseau, stégano…)."),
    Platform("PortSwigger Web Security Academy", "https://portswigger.net/web-security", "Tous niveaux",
             "Le web offensif de A à Z, gratuit, labs interactifs (par les auteurs de Burp)."),
    Platform("OverTheWire (Bandit)", "https://overthewire.org/wargames/bandit/", "Débutant",
             "Apprendre Linux/SSH par le jeu : la base indispensable."),
    Platform("VulnHub", "https://www.vulnhub.com", "Tous niveaux",
             "VMs volontairement vulnérables à télécharger pour ton lab."),
    Platform("picoCTF", "https://picoctf.org", "Débutant",
             "CTF éducatif (crypto, reverse, web, forensics), parfait pour débuter."),
    Platform("Exploit Education", "https://exploit.education", "Intermédiaire",
             "VMs pour apprendre l'exploitation mémoire proprement."),
]

#: Thèmes (compétences + ressources officielles).
THEMES: list[Theme] = [
    Theme("lab", "Monter son lab isolé",
          "Un environnement fermé où tu peux TOUT tester sans rien risquer : "
          "une VM attaquant + une VM cible volontairement vulnérable, sur un réseau "
          "host-only (coupé d'Internet).",
          ["Hyperviseur : VirtualBox (gratuit) ou VMware Workstation Player.",
           "Attaquant : Kali Linux ou Parrot OS (outils préinstallés).",
           "Cibles : Metasploitable2, DVWA, OWASP Juice Shop, VulnHub.",
           "Réseau « host-only » / interne : la cible ne doit pas voir Internet.",
           "Fais des snapshots : tu casses, tu restaures, tu recommences."],
          [("Kali Linux", "https://www.kali.org/get-kali/"),
           ("Metasploitable2", "https://docs.rapid7.com/metasploit/metasploitable-2/"),
           ("DVWA", "https://github.com/digininja/DVWA"),
           ("OWASP Juice Shop", "https://owasp.org/www-project-juice-shop/")]),
    Theme("recon", "Reconnaissance & scan",
          "Cartographier la cible avant d'agir : hôtes, ports, services, versions. "
          "80 % d'un pentest, c'est bien chercher.",
          ["Découverte réseau et de ports : nmap, masscan.",
           "Énumération web : gobuster, ffuf, whatweb.",
           "DNS / sous-domaines : dnsenum, amass (déjà un aperçu dans la CONSOLE).",
           "Prends des notes structurées dès le début (CherryTree, Obsidian)."],
          [("Nmap — doc officielle", "https://nmap.org/book/man.html"),
           ("TryHackMe — Nmap", "https://tryhackme.com/room/furthernmap")]),
    Theme("web", "Sécurité web offensive",
          "La plus grosse surface d'attaque. Comprendre le Top 10 OWASP et savoir "
          "l'exploiter en lab : injections, XSS, contrôle d'accès, SSRF…",
          ["Intercepter/modifier les requêtes : Burp Suite (Community).",
           "Injections SQL : comprendre, puis sqlmap (sur DVWA/Juice Shop).",
           "XSS, CSRF, IDOR, SSRF : les labs PortSwigger couvrent chacun.",
           "Toujours tester sur TES cibles de lab, jamais un site réel."],
          [("OWASP Top 10", "https://owasp.org/www-project-top-ten/"),
           ("PortSwigger — tous les labs", "https://portswigger.net/web-security/all-labs"),
           ("Burp Suite Community", "https://portswigger.net/burp/communitydownload")]),
    Theme("network", "Réseau & services",
          "Attaquer des services réseau en lab : force brute maîtrisée, écoute, "
          "exploitation de services vulnérables, et comprendre le déni de service "
          "pour mieux s'en défendre.",
          ["Services : exploitation via Metasploit sur Metasploitable2.",
           "Mots de passe (en lab) : hydra, john, hashcat.",
           "Écoute/analyse : Wireshark, tcpdump.",
           "DoS : à n'étudier que côté défense + sur TA propre VM (slowhttptest, "
           "hping3) ; jamais contre un tiers (délit, art. 323-2)."],
          [("Metasploit — doc", "https://docs.metasploit.com/"),
           ("Wireshark", "https://www.wireshark.org/")]),
    Theme("privesc", "Élévation de privilèges",
          "Une fois un accès obtenu en lab, passer d'utilisateur à root/admin : "
          "le cœur du métier post-exploitation.",
          ["Linux : énumération (LinPEAS), SUID, cron, capabilities.",
           "Windows : WinPEAS, services mal configurés, tokens.",
           "Méthode > exploit : comprendre pourquoi ça marche."],
          [("GTFOBins", "https://gtfobins.github.io/"),
           ("PEASS-ng (LinPEAS/WinPEAS)", "https://github.com/peass-ng/PEASS-ng"),
           ("TryHackMe — Privesc", "https://tryhackme.com/room/linuxprivesc")]),
    Theme("crypto", "Crypto & reverse",
          "Comprendre comment protéger et casser (en CTF) : hachage, chiffrement, "
          "rétro-ingénierie de binaires.",
          ["Hash/encodage : déjà dans la CONSOLE (hash, hashid, b64…).",
           "Reverse : Ghidra, radare2, gdb.",
           "Challenges : Root-Me (crackme), picoCTF (reverse)."],
          [("Ghidra", "https://ghidra-sre.org/"),
           ("CryptoHack", "https://cryptohack.org/")]),
]

#: Méthodologie de pentest — checklist suivie (progression sauvegardée en local).
CHECKLIST: list[Phase] = [
    Phase("0 · Préparation (légal)", [
        ("prep_scope", "Définir le périmètre : seulement mes machines / un lab / une autorisation écrite"),
        ("prep_lab", "Monter un lab isolé (host-only) avec snapshots"),
        ("prep_notes", "Préparer un carnet de notes structuré"),
    ]),
    Phase("1 · Reconnaissance", [
        ("recon_passive", "Recon passive (OSINT, DNS, WHOIS, sous-domaines)"),
        ("recon_hosts", "Découverte des hôtes vivants sur le réseau du lab"),
    ]),
    Phase("2 · Scan & énumération", [
        ("scan_ports", "Scan de ports/services (nmap) et versions"),
        ("scan_web", "Énumération web (répertoires, technos, endpoints)"),
        ("scan_vulns", "Identifier les vulnérabilités probables"),
    ]),
    Phase("3 · Exploitation (en lab)", [
        ("exp_web", "Exploiter une faille web (SQLi/XSS/IDOR) sur DVWA ou Juice Shop"),
        ("exp_service", "Exploiter un service vulnérable (Metasploitable2)"),
        ("exp_access", "Obtenir un premier accès (shell)"),
    ]),
    Phase("4 · Post-exploitation", [
        ("post_privesc", "Élévation de privilèges (user → root/admin)"),
        ("post_persist", "Comprendre persistance et pivot (notions)"),
    ]),
    Phase("5 · Rapport", [
        ("rep_write", "Rédiger un rapport : faille, impact, preuve, remédiation"),
        ("rep_defense", "Pour chaque faille, noter LA défense (vision blue team)"),
    ]),
]


def total_items() -> int:
    return sum(len(p.items) for p in CHECKLIST)
