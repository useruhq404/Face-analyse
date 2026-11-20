# Benchmark du moteur facial

Mesures réelles, reproductibles avec `scripts/run_benchmark.py`. Données brutes :
[`benchmark.json`](benchmark.json).

| | |
|---|---|
| Détecteur | YuNet 2023mar (OpenCV Zoo, MIT) |
| Embeddings | SFace 2021dec (OpenCV Zoo, Apache-2.0), 128-D, moyenne image + miroir |
| Jeu de données | **LFW** (Labeled Faces in the Wild, UMass Amherst), version *funneled*, jeu public de recherche |
| Protocole | 6 000 paires officielles, 10 plis : le seuil est choisi sur 9 plis, mesuré sur le 10ᵉ |
| Machine | 4 vCPU Intel Xeon 2,1 GHz, CPU uniquement |

Une paire dont un visage n'est pas détecté est comptée comme **rejet** (score −1). Elle
n'est pas exclue, pour ne pas embellir les chiffres.

## 1. Vérification 1:1 (même personne ?)

| Condition | Précision (10 plis) | AUC | EER | Échecs détection | ms / image |
|---|---|---|---|---|---|
| Original | **99,45 % ± 0,40** | 0,9991 | 0,57 % | 0 | 18,4 |
| Sous-exposé (×0,35) | 99,22 % ± 0,30 | 0,9993 | 0,67 % | 0 | 19,7 |
| Basse résolution (÷4) | 98,68 % ± 0,53 | 0,9984 | 1,38 % | 0 | 19,6 |
| JPEG qualité 15 | 98,97 % ± 0,43 | 0,9990 | 1,08 % | 0 | 19,9 |
| Flou gaussien σ=2 | 98,97 % ± 0,50 | 0,9983 | 1,27 % | 0 | 19,5 |
| **Surexposé** (×1,6 +70) | **91,18 % ± 1,39** | 0,9302 | 10,13 % | **185** | 18,4 |

Sans la moyenne image + miroir : 99,45 % ± 0,45, EER 0,63 %, 11,9 ms/image. Le miroir coûte
50 % de temps de calcul, mais il améliore l'EER et la reconnaissance aux seuils stricts.

### Taux d'erreur selon le seuil (condition originale)

| Seuil | Faux positifs (FMR) | Faux négatifs (FNMR) |
|---|---|---|
| 0,363 (valeur OpenCV) | 0,10 % | 0,90 % |
| 0,400 | 0,00 % | 1,57 % |
| 0,450 | 0,00 % | 3,23 % |
| **0,500 (défaut)** | **0,00 %** | **6,20 %** |
| 0,550 | 0,00 % | 11,97 % |
| 0,600 | 0,00 % | 21,60 % |

« 0,00 % » signifie 0 sur 3 000 paires d'imposteurs. Le vrai taux est inférieur à environ 0,1 %
(intervalle de confiance à 95 %), il n'est pas nul.

## 2. Identification en ensemble ouvert : le chiffre qui compte

Le cas d'usage réel consiste à comparer un visage à **toute** la base. La meilleure similarité
parmi N personnes augmente avec N, donc le risque de nommer à tort quelqu'un d'absent augmente
aussi. Le protocole :

* une galerie de 300 identités, avec 3 photos de référence chacune ;
* 300 sondes de personnes enregistrées, avec une photo différente des références ;
* 600 sondes de personnes **absentes** de la galerie.

| Seuil | Enregistrés reconnus | Mauvaise identité | Enregistrés rejetés | **Absents nommés à tort** |
|---|---|---|---|---|
| 0,363 | 99,3 % | 0,33 % | 0,3 % | **49,8 %** |
| 0,400 | 99,3 % | 0,33 % | 0,3 % | 18,0 % |
| 0,450 | 98,7 % | 0,33 % | 1,0 % | 2,7 % |
| **0,500** | **98,0 %** | 0,33 % | 1,7 % | **0,5 %** |
| 0,550 | 97,0 % | 0,33 % | 2,7 % | 0,0 % |
| 0,600 | 93,0 % | 0,33 % | 6,7 % | 0,0 % |

**Conclusion.** Le seuil recommandé par OpenCV (0,363) est adapté à la vérification 1:1. En
recherche dans une base, il nommerait à tort **une personne absente sur deux**. Le seuil par
défaut de l'application est donc fixé à **0,50**. Il est réglable dans SETTINGS, qui affiche ces
chiffres en direct.

## Reproduire

```bash
pip install -r requirements-dev.txt
python -c "from sklearn.datasets import fetch_lfw_pairs as f; f(data_home='lfw', download_if_missing=True)"
python scripts/run_benchmark.py --lfw lfw/lfw_home
```

Avec un modèle personnalisé, choisissez-le dans SETTINGS puis relancez le benchmark : **le
seuil doit être recalibré pour chaque modèle**.
