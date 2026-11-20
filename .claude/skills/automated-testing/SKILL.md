---
name: automated-testing
description: >
  Comment tester FACE ANALYSE : pytest hors écran pour l'UI PySide6, moteur réel
  sur LFW (conditionnel), serveur FastAPI via TestClient, et le piège du teardown Qt.
  Charger avant d'écrire/lancer des tests ou de diagnostiquer un échec CI.
---

# Tests — FACE ANALYSE

## Lancer
```bash
python -m pytest                               # app (Qt offscreen, ~1-2 s)
FACE_ANALYSE_LFW=<lfw_home> python -m pytest   # + visages réels (test_engine, camera)
cd server && python -m pytest                  # serveur (FastAPI TestClient)
```
LFW : `python -c "from sklearn.datasets import fetch_lfw_pairs as f; f(data_home='lfw')"`
→ passer `<lfw_home>` = `lfw/lfw_home`. Sans la variable, ces tests sont *skipped*.

## Conventions
- Interface : `QT_QPA_PLATFORM=offscreen`. Fixture `qapp` (module) + fixture autouse
  `_cleanup_widgets` qui **ferme et détruit** les widgets après chaque test.
  **Impératif** : sans ce nettoyage, Qt plante au démontage
  (« pure virtual method called » → `pytest` exit 134 → CI rouge). Tout nouveau test
  UI qui crée des widgets top-level doit s'appuyer dessus (déjà autouse dans test_ui.py).
- Isolation des données : fixture `isolated_home` (env `FACE_ANALYSE_HOME` → tmp) et
  `Repository(tmp_path/"x.db")`. Jamais d'écriture dans le vrai dossier utilisateur.
- Déterminisme : `FakeEngine` (embedding dérivé de l'image) pour la base ; `FakeHttp`
  pour l'OSINT ; graines fixes pour le layout du graphe.
- Réseau : les tests ne sortent pas sur Internet (sources OSINT mockées). Les appels
  réels se vérifient à la main, hors suite.

## Ce qu'on teste
- `matcher` (MATCH/AMBIGUOUS/UNKNOWN, seuil, refus inter-modèles), `tracking` (vote),
  `preprocessing`/`quality`, `database` (chiffrement, suppression, RGPD), `engine`
  (LFW : même personne > seuil > autre), `osint` (sources mockées, dédoublonnage),
  `dataset` (chargeur + stats), `graph` (construction + sélection), `timeline`,
  `benchmark` (métriques), `config`, `auth client`, `ui` (fumée des pages).
- Serveur : auth, télémétrie, admin (un user ne voit aucune IP), RGPD.

## Avant de dire « fini »
`python -m pytest` **exit 0** (pas seulement « N passed »), et `cd server && pytest`.
Le workflow GitHub `windows-build` compile l'exe + lance l'app 15 s ; `server-tests`
lance les tests serveur.
