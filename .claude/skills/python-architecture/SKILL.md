---
name: python-architecture
description: >
  Conventions d'architecture et de code Python de FACE ANALYSE : séparation du
  moteur, concurrence UI, chemins Windows/PyInstaller, chiffrement, extensibilité
  des modèles. Charger avant un refactor, un nouveau module ou une revue d'archi.
---

# Architecture Python — FACE ANALYSE

## Règles de structure
- **Universal Face Engine** (`engine/`) : les trois étages (détection → embedding →
  identité) ne communiquent que par les structures de `engine/types.py` et les
  contrats de `engine/interfaces.py`. Ajouter un modèle = sous-classe + entrée dans
  `engine/registry.py` ; rien d'autre ne change. Un embedding porte son `model_id` ;
  le matcher refuse de mélanger deux modèles.
- **UI jamais bloquée** : tout IO/réseau/calcul lourd passe par `ui/workers.run_async`
  (QThreadPool) ou le `QThread` caméra. Les slots mettent seulement à jour l'UI.
  `run_async` garde une référence forte au worker (sinon le GC détruit ses signaux).
- **État partagé** : `ui/context.AppContext` (settings, repo, moteur chargé en fond,
  auth optionnelle, signaux `notify`/`busy`/`gallery_changed`). Les pages passent par lui.
- **Chemins** : `core/paths.py` — ressources via `resource_path` (gère `_MEIPASS`
  PyInstaller), données via `user_data_dir` (`%LOCALAPPDATA%` Windows). Jamais de
  chemin absolu codé en dur ; `pathlib` partout ; lecture image via octets (Unicode Win).
- **Données** : `database/repository.py` (SQLAlchemy 2, sessions courtes, lock).
  Biométrie et secrets chiffrés (`database/crypto.Vault`, Fernet + DPAPI). Suppression
  en cascade + `secure_delete` + `VACUUM`.
- **Erreurs** : hiérarchie `core/errors.FaceAnalyseError` (message utilisateur FR).
  Les workers attrapent et émettent `failed`. Journaux via `core/logging_setup`.

## Style
- `from __future__ import annotations`, type hints partout, dataclasses pour les
  structures. Docstrings en français, concises. Pas de dépendance lourde sans raison.
- Nommage FR pour l'UI visible, EN/FR cohérent pour l'interne. Ligne ≤ 130.
- Nouveau module d'interface : un fichier par page sous `ui/pages/`, widgets
  réutilisables sous `ui/widgets/`. Pas de logique métier dans l'UI (déléguer au
  moteur / repo / modules `osint`, `dataset`, `graph`).

## Dépendances (exécution)
PySide6, opencv-contrib-python-headless, numpy, SQLAlchemy, cryptography, requests,
anthropic (option), onnxruntime (modèles ONNX). Serveur : fastapi, uvicorn, httpx,
itsdangerous, python-multipart. Toute nouvelle dépendance doit être justifiée et
ajoutée à `requirements*.txt` / `server/requirements.txt`.
