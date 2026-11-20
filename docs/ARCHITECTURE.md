# Architecture

```
face_analyse/
├── core/            chemins Windows/PyInstaller, configuration JSON, journaux, erreurs
├── engine/          UNIVERSAL FACE ENGINE (sans dépendance à l'interface)
│   ├── interfaces.py      contrats FaceDetector / FaceEmbedder
│   ├── detectors/yunet.py       ① détection (tous les visages, connus ou non)
│   ├── embedders/sface.py       ② empreintes (SFace)
│   ├── embedders/onnx_arcface.py   ② tout modèle ONNX type ArcFace (remplaçable sans recompiler)
│   ├── matcher.py               ③ recherche d'identité, seuil, UNKNOWN, ambiguïté
│   ├── pipeline.py        orchestration ①→②→③ + mesures de temps
│   ├── registry.py        catalogue des modèles + vérification SHA-256
│   ├── quality.py         taille, netteté, exposition, rotation
│   ├── preprocessing.py   chargement (chemins Unicode), correction de lumière
│   ├── tracking.py        suivi vidéo (IoU) + vote temporel
│   └── benchmark.py       protocole LFW (vérification, ensemble ouvert, robustesse)
├── database/        SQLite + SQLAlchemy, chiffrement Fernet (clé protégée par DPAPI sous Windows)
├── osint/           sources API officielles, pseudonymes, liens navigateur, dédoublonnage,
│                    rapports HTML/JSON, assistant IA (Claude)
└── ui/              PySide6 : écran d'accueil, dashboard, pages, thread caméra, widgets
```

## Séparation des étages

Les trois étages communiquent uniquement par des structures de données (`engine/types.py`) :

| Étage | Entrée | Sortie |
|---|---|---|
| Détection | image BGR | `DetectedFace` (boîte, 5 points, score) |
| Embedding | image + `DetectedFace` | `FaceEmbedding` (vecteur L2, `model_id`) |
| Identité | `FaceEmbedding` + galerie | `IdentityDecision` (MATCH / AMBIGUOUS / UNKNOWN) |

Chaque embedding est stocké avec le `model_id` du modèle qui l'a produit. Le matcher **refuse**
de comparer des empreintes issues de modèles différents, car leurs espaces sont incompatibles.

## Remplacer le modèle

1. **Sans recompiler** : déposez un `.onnx` de type ArcFace (entrée 112×112, sortie D-dim) dans
   `%LOCALAPPDATA%\FaceAnalyse\models`, puis sélectionnez-le dans SETTINGS. FACE DATABASE propose
   alors de **recalculer les empreintes** à partir des photos chiffrées conservées : aucun
   ré-enrôlement n'est nécessaire.
2. **Nouveau type de modèle** : écrivez une sous-classe de `FaceDetector` ou de `FaceEmbedder`
   et ajoutez-la dans `registry.py`. Rien d'autre ne change.
3. Recalibrez le seuil avec `scripts/run_benchmark.py`.

## Performances

* YuNet : environ 15 ms (720p) ; SFace + miroir : environ 18 ms par visage (CPU 2,1 GHz).
* Recherche : produit matriciel vectorisé, moins d'1 ms pour 10 000 références.
* Caméra : détection à chaque image, reconnaissance toutes les N images par visage suivi,
  cadre lissé.
* Interface : tous les traitements lourds s'exécutent dans `QThreadPool` ou dans un `QThread`
  dédié à la caméra.

## Sécurité des données

* Photos, embeddings et clés API sont chiffrés (Fernet). La clé est protégée par DPAPI (compte
  Windows).
* `PRAGMA secure_delete=ON` et `VACUUM` après chaque suppression. La suppression d'une personne
  purge aussi les entrées d'historique qui la nomment (vérifié par un test).
* Aucune image n'est envoyée sur le réseau. L'assistant IA ne reçoit que du texte : le nom
  recherché et les résultats publics.
