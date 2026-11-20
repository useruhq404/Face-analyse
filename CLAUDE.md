# FACE ANALYSE — mémoire projet (CLAUDE.md)

Application de bureau d'**analyse faciale locale** (base de personnes consentantes)
et de **recherche OSINT par sources publiques**, signée *Aruka* (« discord: 35ans »).
Direction artistique : noir, pixel-art, dot-matrix, monospace, minimalisme cinématique.

> **Avant de coder une page ou un composant d'interface, charge le skill
> `project-design-system`.** Il contient les règles exactes de la DA : ne jamais
> la dégrader.

## Pile technique
- Python 3.12+ · **PySide6** (interface) · **OpenCV contrib** (YuNet + SFace)
- SQLAlchemy 2 + SQLite **chiffré** (Fernet, DPAPI sous Windows)
- numpy · requests · cryptography · onnxruntime (modèles ONNX custom)
- Serveur de comptes séparé (`server/`) : **FastAPI** + uvicorn
- PyInstaller (exe Windows) · GitHub Actions (`windows-build`, `server-tests`)

## Architecture
```
face_analyse/
  core/        chemins (Windows/PyInstaller), config JSON, logs, erreurs
  engine/      Universal Face Engine : détecteurs / embedders / matcher SÉPARÉS
               (interfaces.py), pipeline, registry (SHA-256), quality, tracking,
               benchmark (LFW), preprocessing
  database/    repository (chiffré), models, crypto (Fernet + DPAPI)
  osint/       sources (API officielles), usernames (+ liens profil direct), iplookup,
               links, aggregator, report (HTML/JSON), assistant (API Claude),
               email/phone/images/pdf, netinfo (DNS-over-HTTPS, RDAP, crt.sh, en-têtes,
               scan ports LOCAL), crypto_tools (hash/encodage, hors ligne),
               generators (IP/IBAN factice/UUID/MAC + décodeur ID Discord), learn
  dataset/     loader (CSV/JSON/TXT) + analysis (stats, histogramme, doublons)
  graph/       model (nœuds/liens) + layout (force-dirigé numpy)
  auth/        client du serveur de comptes + device info
  ui/          theme, context (AppContext), splash, main_window, workers,
               widgets/ (dot_field, pixel_title, charts, command_palette, ...),
               pages/ (overview, analysis, camera, database, osint, graph, datalab,
                       timeline, tools, console, loadtest, history, guide, settings)
server/        serveur FastAPI (comptes, sessions, panel admin, OAuth)
docs/          BENCHMARK.md, LIMITES.md, ARCHITECTURE.md, benchmark.json
```

## Principes d'ingénierie (ne pas casser)
- **Trois étages du moteur strictement séparés** : détection → embedding → identité.
  Un embedding porte le `model_id` ; le matcher refuse de comparer deux modèles différents.
- **Travaux lourds hors du thread UI** : `ui/workers.run_async(...)` (QThreadPool) ou
  le `QThread` dédié caméra. Jamais de réseau/IO bloquant dans un slot.
- Chaque page hérite de `ui/pages/common.Page` (titre + sous-titre + bouton « ? »).
  Enregistrer une page dans `main_window.NAV` et dans la grille `pages/overview.MODULES`.
- Données biométriques et secrets **chiffrés au repos**. Suppression = cascade + VACUUM.
- Modèles vérifiés par **SHA-256** au chargement ; remplaçables sans recompiler (ONNX).

## Limites éthiques et légales — INTANGIBLES
- Le moteur facial ne nomme **que** des personnes enregistrées **avec consentement**
  dans la base locale. Un visage inconnu est **UNKNOWN**. Jamais d'identification de
  personnes inconnues contre des bases externes/scrapées.
- **Aucun** scraping des réseaux sociaux / annuaires ni contournement d'authentification,
  d'anti-robots ou de limites d'API. Les plateformes sans API publique sont proposées
  en **liens** à ouvrir dans le navigateur, pas interrogées automatiquement.
- Un score de similarité **n'est pas** une probabilité d'identité. Une correspondance
  de nom OSINT **n'est pas** une preuve (homonymes). Ne jamais présenter une hypothèse
  comme un fait.
- RGPD : consentement horodaté, droit à la suppression complète, journalisation
  transparente côté serveur (affichée à la connexion).

## Commandes
```bash
python -m face_analyse                 # lancer l'app (mode autonome sans serveur)
python -m pytest                       # tests app (offscreen Qt)
FACE_ANALYSE_LFW=<lfw_home> python -m pytest   # + tests sur visages réels (LFW)
python scripts/run_benchmark.py --lfw <lfw_home>   # benchmark LFW
cd server && python start_local.py     # serveur de comptes local (+ /admin)
cd server && python -m pytest          # tests serveur (FastAPI TestClient)
pyinstaller --noconfirm face_analyse.spec          # exe Windows (sur Windows)
```
Hôtes réseau utiles (environnement) : huggingface.co + cdn (modèles), API OSINT
(fr/en.wikipedia.org, www.wikidata.org, api.github.com, pub.orcid.org,
api.openalex.org, api.archives-ouvertes.fr, recherche-entreprises.api.gouv.fr,
bodacc-datadila.opendatasoft.com), ip-api/ipwho.is/ipinfo.io, api.anthropic.com.

## Qualité (critères de « fini »)
- Fonctionnalité réelle : aucun bouton factice, aucun faux chargement, aucune
  statistique inventée ; états vides soignés plutôt que fausses données.
- Tests verts (`python -m pytest`, exit 0 — fermer/détruire les widgets en teardown).
- Gestion d'erreurs + états loading/empty/error sur chaque page.
- La DA respectée (cf. skill `project-design-system`) : revue visuelle avant « fini ».
- Git : développer sur `claude/face-analyse-windows-app-ekuqzm`, commits en français,
  pousser ; ne pas committer de secrets ni de base (`.gitignore`).

## Agents & skills de projet
- Skills : `project-design-system`, `osint-research`, `automated-testing`,
  `python-architecture` (dans `.claude/skills/`).
- Sous-agents : `.claude/agents/` (architecte, dev Python, UI/UX, OSINT, data, QA, sécurité).
