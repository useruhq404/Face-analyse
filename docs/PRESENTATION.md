# FACE ANALYSE — présentation complète du projet

**Auteur :** Aruka (« discord: 35ans »)
**Nature :** application de bureau Windows, locale, pour l'**analyse faciale sur base
consentante** + la **recherche OSINT en sources publiques légales**.
**Direction artistique :** noir, pixel-art, dot-matrix, monospace, minimalisme
cinématique, graphiques monochromes.

---

## 1. En une phrase

Un poste de travail d'investigation numérique qui tourne **entièrement en local** :
il reconnaît des visages **uniquement** parmi des personnes enregistrées avec leur
consentement, et il agrège des informations issues **d'API publiques officielles**
(aucun scraping, aucun contournement), le tout dans une interface soignée et un
terminal d'apprentissage cyber.

---

## 2. Pile technique

- **Python 3.12+** · **PySide6** (interface Qt)
- **OpenCV contrib** : détection **YuNet** + empreintes **SFace** (128-D, cosinus)
- **SQLAlchemy 2 + SQLite chiffré** au repos (Fernet + DPAPI sous Windows)
- **numpy, requests, httpx, cryptography, onnxruntime, phonenumbers**
- **Serveur de comptes séparé** : **FastAPI** + uvicorn (OAuth Discord/Google, panel admin)
- **PyInstaller** (.exe Windows) · **GitHub Actions** (build Windows + tests serveur)

---

## 3. Architecture (modules)

```
face_analyse/
  core/        chemins Windows/PyInstaller, config JSON, logs, erreurs
  engine/      moteur facial : détecteur / embedder / matcher SÉPARÉS,
               pipeline, registry (SHA-256), qualité, tracking, benchmark LFW
  database/    repository chiffré, modèles, crypto (Fernet + DPAPI)
  osint/       sources (API off.), usernames + liens profil, iplookup, links,
               aggregator, report HTML/JSON, assistant IA (API Claude),
               email/phone/images/pdf, netinfo, crypto_tools, generators, learn
  dataset/     import CSV/JSON/TXT + statistiques
  graph/       nœuds/liens + layout force-dirigé (numpy)
  auth/        client du serveur de comptes + infos machine
  ui/          thème, contexte, splash, fenêtre principale, workers,
               widgets + pages
server/        serveur FastAPI (comptes, sessions, admin, OAuth)
docs/          BENCHMARK, LIMITES, ARCHITECTURE
```

**Principes d'ingénierie respectés :**
- Les **trois étages du moteur sont strictement séparés** : détection → embedding →
  identité. Un embedding porte son `model_id` ; le matcher **refuse** de comparer
  deux modèles différents.
- **Aucun travail lourd dans le thread UI** : tout passe par `run_async` (QThreadPool)
  ou le thread caméra dédié.
- **Données biométriques et secrets chiffrés au repos** ; suppression = cascade + VACUUM.
- **Modèles vérifiés par SHA-256** au chargement, remplaçables sans recompiler (ONNX).

---

## 4. Les 14 modules de l'interface

1. **SYSTEM OVERVIEW** — écran d'accueil cinématique : statut système, activité réelle
   (14 jours), répartition par module, grille des modules, activité récente. Données
   **réelles** (base + historique), états vides soignés plutôt que fausses stats.
2. **FACE ANALYSIS** — détection, empreintes, correspondances sur une image.
3. **LIVE CAMERA** — reconnaissance en direct contre la base consentante (thread dédié,
   tracking). Un visage non enregistré = **UNKNOWN**.
4. **FACE DATABASE** — personnes, photos, empreintes chiffrées, consentement horodaté.
5. **OSINT SEARCH** — recherche par nom via API publiques (Wikipedia, Wikidata,
   Annuaire des Entreprises, BODACC, ORCID, HAL, OpenAlex, GitHub), dédoublonnage,
   classement, assistant IA, export de rapport HTML/JSON.
6. **INTEL GRAPH** — graphe relationnel interactif (layout force-dirigé).
7. **DATA LAB** — import CSV/JSON/TXT, statistiques, histogrammes, doublons.
8. **TIMELINE** — chronologie interactive des événements.
9. **IP · USERNAME (OUTILS)** — onglets :
   - **IP LOOKUP** (géoloc/opérateur via ipwho.is/ipinfo.io)
   - **USERNAME TRACKER** (vérifie l'existence d'un pseudo + **45 liens profil direct**
     vers tous les réseaux : Instagram, TikTok, Snapchat, LinkedIn, Discord, X, Twitch,
     Steam, Roblox, SoundCloud, GitHub… classés en 10 catégories)
   - **E-MAIL** (profil Gravatar public + pistes)
   - **TÉLÉPHONE** (métadonnées hors ligne via phonenumbers)
   - **IMAGE INVERSÉE** (liens vers les moteurs de recherche d'image)
   - **GÉNÉRATEURS** (voir §6)
10. **CONSOLE** — terminal stylé d'apprentissage et d'outils (voir §5).
11. **STRESS TEST** — test de charge **multi-cibles** de TES propres services
    (débit, latence p50/p90/p99, codes, erreurs, histogramme). Garde-fou : toute
    cible non locale exige la case « je possède / suis autorisé ».
12. **HISTORY** — journal local horodaté de toutes les actions.
13. **GUIDE / INFO** — rôle et fonctionnement de chaque module (fiches d'aide).
14. **SETTINGS** — moteur, seuil de décision (taux d'erreur mesurés sur LFW), caméra,
    OSINT, compte, clés API chiffrées, effacement des données.

Plus : **palette de commandes** (Ctrl+K / Ctrl+P), **emblème cybersécurité original**
(visage scanné dans un réticule, dot-matrix), **titre pixel-art** + signature
« discord: 35ans ».

---

## 5. Le module CONSOLE (terminal d'apprentissage)

Un vrai interpréteur de commandes (historique ↑/↓, bannière ASCII), dans la DA :

- **Recon réseau** (API publiques, hors thread UI) :
  `ip`, `dns` (DNS-over-HTTPS), `whois` (RDAP), `subdomains` (crt.sh),
  `headers` (en-têtes de sécurité HTTP présents/absents), `cert` (certificat TLS),
  `ports` (scan TCP **limité aux hôtes locaux/privés**, ou explicitement autorisés).
- **Crypto / encodage** (100 % hors ligne) :
  `hash` (md5/sha1/sha256/sha512), `hashid`, `b64/url/hex/binary/morse enc|dec`,
  `rot13`, `pwgen` (+ entropie).
- **Générateurs** : `genip`, `geniban`, `uuid`, `mac`, `discord <id>`.
- **Apprendre** : `learn` → fiches **osint, recon, web, crypto, passwords, dos, ethics**,
  chacune renvoyant vers une commande réelle à essayer.

---

## 6. GÉNÉRATEURS & décodeurs (données de test, hors ligne)

- **IP** aléatoires (IPv4 publiques/privées, IPv6)
- **IBAN factice** à clé de contrôle mod-97 **valide** (12 pays) — ne correspond à
  **aucun compte réel**, pour tester des formulaires
- **UUID v4** et **adresses MAC**
- **Décodeur d'ID Discord** (snowflake → date de création exacte, ancienneté,
  worker/process/incrément). L'horodatage est **encodé dans l'ID** (doc publique) :
  aucun appel à Discord, ne révèle ni le nom ni le titulaire.

---

## 7. Serveur de comptes (optionnel)

Serveur **FastAPI** séparé : inscription/connexion (e-mail, **Discord**, **Google**
OAuth), mots de passe PBKDF2, jetons de session hachés, **panel admin** où le
propriétaire voit qui est connecté, depuis quelle machine/IP, peut suspendre un
compte ou fermer une session. Journalisation **transparente** présentée à la connexion
(RGPD). Sans serveur configuré, l'app tourne en **mode autonome**, sans compte.

---

## 8. Limites éthiques et légales — INTANGIBLES

- Le moteur facial ne nomme **que** des personnes enregistrées **avec consentement**.
  Un visage inconnu reste **UNKNOWN**. **Jamais** d'identification d'inconnus contre
  des bases externes/scrapées.
- **Aucun scraping** de réseaux/annuaires, **aucun contournement** d'authentification,
  d'anti-robots ou de limites d'API. Les plateformes sans API publique sont proposées
  en **liens à ouvrir soi-même**, jamais interrogées automatiquement.
- Un score de similarité **n'est pas** une probabilité d'identité ; une correspondance
  de nom OSINT **n'est pas** une preuve (homonymes).
- **Absents volontairement** (illégaux) : DDoS/booter, token grabber, webhook
  spam/raid, nuke, bombers mail/SMS, phishing, bruteforce. Pour tester la charge de
  **tes** services → module STRESS TEST ; pour apprendre l'offensif → CTF + pentest
  autorisé (fiche `learn ethics`).
- RGPD : consentement horodaté, droit à la suppression complète, journalisation
  transparente.

---

## 9. Qualité & industrialisation

- **Fonctionnalités réelles** : aucun bouton factice, aucun faux chargement, aucune
  stat inventée ; états loading/empty/error sur chaque page.
- **Tests verts** (`python -m pytest`, exit 0, Qt hors écran) : moteur, base, OSINT,
  générateurs, netinfo, console, UI ; tests moteur sur **visages réels LFW**
  (conditionnels) ; tests serveur via FastAPI TestClient.
- **Benchmark LFW** (seuil/erreurs mesurés, pas inventés).
- **CI GitHub Actions** : build Windows (.exe PyInstaller) + tests serveur à chaque push.
- **.exe Windows** généré et livrable.

---

## 10. État du projet

**Complet et fonctionnel.** Les 14 modules sont en place, testés, dans la DA ; le
périmètre légal est tenu ; le build Windows passe et l'exécutable est produit.
Pistes d'évolution possibles : plus de sources OSINT, réglages visuels, activation du
serveur de comptes, nouveaux modèles ONNX.
