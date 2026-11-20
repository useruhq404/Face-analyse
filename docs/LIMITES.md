# Limites du modèle et risques de faux positifs

## Ce que le score signifie (et ne signifie pas)

* Le score affiché est une **similarité cosinus** entre deux empreintes de 128 nombres. Il va de
  −1 à 1. **Ce n'est pas une probabilité d'identité.** Un score de 0,62 ne veut pas dire « 62 %
  de chances que ce soit la même personne ».
* Au-dessus du seuil, l'application affiche une **correspondance potentielle**. En dessous, elle
  affiche **UNKNOWN** et ne propose aucun nom.
* L'application ne peut nommer **que** des personnes enregistrées volontairement dans la base
  locale. Elle ne cherche jamais l'identité d'un visage ailleurs (ni Internet, ni réseaux
  sociaux, ni moteurs de recherche faciale).

## Faux positifs : quand et pourquoi

1. **Taille de la base.** Plus la base contient de personnes, plus il est probable qu'un inconnu
   ressemble assez à l'une d'elles. Sur LFW, au seuil 0,363, une personne absente sur deux était
   nommée à tort avec 300 identités en base (voir [BENCHMARK.md](BENCHMARK.md)). Pour une base
   beaucoup plus grande, relevez le seuil et recalibrez-le.
2. **Proches parents et jumeaux** : le modèle ne sait pas les distinguer de façon fiable.
3. **Sosies, maquillage, déguisement, chirurgie.**
4. **Ambiguïté.** Quand deux personnes enregistrées obtiennent des scores proches (écart inférieur
   à la marge réglable), le statut est **AMBIGUOUS** et une vérification humaine est demandée.

## Faux négatifs (personne enregistrée non reconnue)

* **Surexposition.** C'est le point faible mesuré : 91 % de précision et 6 % de visages non
  détectés en photo brûlée.
* Profil marqué (rotation supérieure à environ 45°), visage partiellement masqué (masque, mains,
  lunettes de soleil).
* Visage très petit (moins de 40 px), flou de bougé, fort contre-jour.
* Écart d'âge important entre les photos de référence et la photo analysée.
* **Atténuation** : enregistrer plusieurs photos par personne (angles, lumières et époques
  différents). L'application calcule pour chaque visage des indicateurs de qualité (taille,
  netteté, luminosité, rotation) et affiche un avertissement quand ils sont défavorables.

## Biais

Les modèles de reconnaissance faciale entraînés sur des données publiques ont des taux d'erreur
**inégaux selon l'âge, le genre et la couleur de peau**. SFace a été entraîné sur MS-Celeb-1M,
une base dominée par des adultes célèbres. LFW, utilisé pour le benchmark, a le même biais : les
chiffres annoncés ne garantissent pas les mêmes performances sur toutes les populations. Ne
prenez **aucune décision importante** sur la seule base d'un score.

## Caméra en direct

L'étiquette affichée résulte d'un **vote sur plusieurs images**. Un nom n'apparaît que s'il est
majoritaire sur les dernières décisions, ce qui évite qu'une seule image chanceuse nomme
quelqu'un. Le modèle n'a **aucune détection de vivacité** : une photo d'une personne enregistrée
présentée à la caméra sera reconnue. N'utilisez pas ce logiciel comme contrôle d'accès.

## OSINT

* Un résultat signifie : « une page publique mentionne ce nom ». Les **homonymes** sont fréquents.
* La vérification de pseudonyme indique seulement qu'un compte porte ce pseudo, pas qu'il
  appartient à la personne.
* L'assistant IA peut se tromper. Ses suggestions sont des pistes à vérifier, et ses synthèses
  se limitent aux résultats collectés.
* LinkedIn, Facebook, Instagram, TikTok, X, Pages Jaunes et Pages Blanches ne sont **jamais
  interrogés automatiquement** : leurs conditions d'utilisation l'interdisent. L'application
  fournit des liens de recherche à ouvrir soi-même.

## Cadre légal (France / UE)

Les empreintes faciales sont des **données biométriques** (art. 9 RGPD). Leur traitement exige
le **consentement explicite** de chaque personne enregistrée : l'application le recueille et
l'horodate. Chaque personne peut obtenir la suppression complète de ses données, ce que permet
le bouton « Supprimer toutes ses données ». L'utilisation de l'OSINT doit respecter la vie
privée des personnes recherchées.
