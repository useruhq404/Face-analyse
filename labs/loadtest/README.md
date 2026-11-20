# Lab — Load testing (test de charge)

Un vrai outil d'**entraînement cyber** : mesurer comment un service tient la charge.
Même base technique que « envoyer beaucoup de requêtes », mais **mesurée, légale et
pédagogique**. Tu apprends : concurrence, keep-alive, latence (moyenne vs p99),
débit (req/s), point de saturation, limites de débit (429), timeouts.

## Contenu
- `target_server.py` — une **cible d'entraînement** locale (ton propre système).
- `loadtest.py` — le **testeur de charge** (concurrence, durée/volume, montée en
  charge, plafond de débit) qui sort des métriques réelles.

## Utilisation (dans ta VM)
```bash
pip install httpx

# Terminal 1 — lance ta cible (simule 3 ms de traitement par requête) :
python target_server.py --work-ms 3 --port 8090
#   --max-rps 500   pour voir la cible renvoyer des 429 au-delà d'un seuil

# Terminal 2 — teste-la :
python loadtest.py http://127.0.0.1:8090 --concurrency 50 --requests 2000
python loadtest.py http://127.0.0.1:8090 --concurrency 100 --duration 15 --ramp 5
python loadtest.py http://127.0.0.1:8090 --concurrency 30 --duration 10 --rps 300
```

Exemple de sortie : `Débit 519 req/s · Latence p50 19ms · p90 32ms · p99 1272ms`.
Fais varier la concurrence et observe où la latence explose : c'est le **point de
rupture** de ta cible.

## Règle (lis-la)
Ne vise **que** des systèmes qui t'appartiennent ou que tu es **explicitement
autorisé** à tester. Une cible non locale est refusée sans `--authorized`.
Envoyer du trafic pour saturer un système tiers est un **déni de service**,
illégal (France : art. 323-2, jusqu'à 5 ans et 150 000 €). Cet outil s'arrête,
rapporte, et respecte un plafond de débit — il sert à **mesurer**, pas à nuire.

## Pour aller plus loin (outils pros)
- **k6** (Grafana), **Locust** (Python), **wrk**, **JMeter** — standards du métier.
- Côté défense : rate limiting, WAF, Cloudflare, SYN cookies, fail2ban — comprendre
  comment on **encaisse** et on **détecte** une surcharge.

## S'entraîner à l'offensif/défensif, légalement
Labs isolés et plateformes faites pour ça : **TryHackMe**, **Hack The Box**,
**PortSwigger Web Security Academy** (gratuit), **OverTheWire**, **VulnHub**,
**DVWA**, **Juice Shop**. Monte un lab attaquant + cible **que tu possèdes** dans
ta VM. C'est comme ça qu'on apprend la cyber sans finir devant un juge.
