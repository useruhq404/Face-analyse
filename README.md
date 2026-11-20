# FACE ANALYSE

*fait par Aruka*

Logiciel Windows d'analyse faciale **locale**, fondé sur une base de personnes **consentantes**,
avec un module OSINT de recherche **par nom** dans des sources publiques autorisées.

## Fonctionnalités

| Module | Ce qu'il fait réellement |
|---|---|
| **Écran d'accueil** | Fenêtre 750×450, fond « halftone » animé. Choix 1–6 au clavier ou à la souris, bouton ENTER |
| **FACE ANALYSIS** | Détection de tous les visages d'une photo, indicateurs de qualité, recherche dans la base, top-K avec scores, statut MATCH / AMBIGUOUS / UNKNOWN. Comparaison 1:1 de deux photos |
| **LIVE CAMERA** | Autorisation demandée avant activation. Cadre qui suit chaque tête, nom affiché si la personne est enregistrée. Bascule entre caméras (avant / arrière / USB), mode miroir, enrôlement direct depuis la caméra |
| **FACE DATABASE** | Personnes et consentement horodaté, plusieurs photos par personne, stockage chiffré, modification, recherche, suppression complète, recalcul des empreintes après changement de modèle |
| **OSINT SEARCH** | Wikipedia FR/EN, Wikidata, Annuaire des Entreprises (data.gouv), BODACC, ORCID, HAL, OpenAlex, GitHub. Pseudonymes vérifiés sur 19 plateformes. Liens navigateur pour LinkedIn, Facebook, Instagram, TikTok, X, YouTube, Pages Jaunes, Pages Blanches, Societe.com, Pappers… Dédoublonnage, horodatage, rapport HTML/JSON, assistant IA (Claude) |
| **IP · USERNAME** | **IP Lookup** (géoloc, ASN/opérateur, DNS inverse, carte) et **Username Tracker** (existence d'un pseudo sur ~19 plateformes) |
| **GUIDE / INFO** | Explication de chaque module : à quoi il sert, comment il marche, comment l'utiliser (aussi via le bouton « ? » de chaque page) |
| **HISTORY** | Journal local horodaté de toutes les opérations |
| **SETTINGS** | Seuil avec taux d'erreur mesurés affichés en direct, choix du modèle, caméra, clés API chiffrées, effacement des données |

## Performances mesurées (LFW, CPU)

* Vérification 1:1 : **99,45 %** de précision (10 plis), EER 0,57 %, environ 18 ms par visage.
* Recherche dans une base de 300 personnes au seuil par défaut 0,50 : **98 %** des personnes
  enregistrées reconnues, **0,5 %** des personnes absentes nommées à tort.
* Détails, robustesse (lumière, résolution, compression, flou) et méthode :
  [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Comptes, accès et administration (facultatif)

Un **serveur** (dossier `server/`) ajoute une couche de comptes et de contrôle :

* connexion par **e-mail, Discord ou Google** (OAuth) avec pseudo + avatar ;
* **panel admin** (`/admin`) réservé au propriétaire : qui est en ligne, depuis quelle
  machine et quelle IP (géolocalisée), journal d'activité, **suspension/ révocation à distance** ;
* journalisation **transparente** : l'utilisateur voit à la connexion ce qui est enregistré (RGPD) ;
* le contenu des images et des recherches **n'est jamais** envoyé au serveur, seulement les actions.

Sans serveur configuré, l'application reste **autonome** (aucun compte requis). Voir
[`server/README.md`](server/README.md) pour le déploiement.

> **Protection du projet.** Un `.exe` peut être décompilé : la vraie protection vient du serveur.
> Tant que vous ne distribuez pas le serveur ni `FA_SECRET_KEY`, personne ne peut créer de session
> valide, et vous pouvez révoquer un accès à tout moment.

## Ce que le logiciel ne fait pas, volontairement

* Il **n'identifie pas** les personnes absentes de la base consentante : elles s'affichent
  **UNKNOWN**.
* Il ne fait **aucune recherche de visage sur Internet** (type PimEyes ou FaceCheck), et
  l'OSINT n'est jamais relié au moteur facial.
* Il ne **scrape** pas les réseaux sociaux et ne contourne aucune restriction d'accès.
* Un score de similarité **n'est pas une probabilité d'identité**. Voir
  [docs/LIMITES.md](docs/LIMITES.md).

## Installation (développement)

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m face_analyse
```

Les modèles officiels (YuNet, SFace) sont fournis dans `face_analyse/resources/models/` et
vérifiés par SHA-256 à chaque chargement. Pour les retélécharger :
`python scripts/download_models.py`.

## Exécutable Windows

* **Automatique** : le workflow GitHub Actions `windows-build` compile l'exécutable sur
  Windows, lance les tests, vérifie que le `.exe` démarre, puis publie l'artefact
  `FaceAnalyse-windows`.
* **Local** : double-cliquez sur `build_windows.bat`. Résultat :
  `dist\FaceAnalyse\FaceAnalyse.exe`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest                              # 60 tests unitaires
FACE_ANALYSE_LFW=chemin/lfw_home python -m pytest   # + 5 tests sur visages réels (dont caméra simulée)
```

## Données

Tout est stocké localement dans `%LOCALAPPDATA%\FaceAnalyse` : base SQLite chiffrée, clé
protégée par DPAPI, journaux, rapports. Aucune image ne quitte l'ordinateur.

## Licences des modèles

* YuNet : MIT (OpenCV Zoo).
* SFace : Apache-2.0 (OpenCV Zoo).

Voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour remplacer le modèle.
