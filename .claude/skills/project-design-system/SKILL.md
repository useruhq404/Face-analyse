---
name: project-design-system
description: >
  Règles EXACTES de la direction artistique de FACE ANALYSE (noir, pixel-art,
  dot-matrix, monospace, minimalisme cinématique, graphiques monochromes).
  Charger AVANT d'écrire ou de modifier toute page, widget ou style de l'interface
  PySide6, pour ne jamais dégrader l'identité visuelle.
---

# FACE ANALYSE — Design System

L'écran d'accueil (fond noir, titre pixel-art « dégoulinant », trame de points,
navigation numérotée, monospace) est la **référence**. Toute nouvelle surface
doit sembler dessinée par le même directeur artistique.

## Source de vérité
- Couleurs, feuille de style et polices : `face_analyse/ui/theme.py` (ne pas
  définir de couleurs en dur dans une page ; utiliser les tokens du thème).
- Composants réutilisables : `face_analyse/ui/widgets/` et `ui/pages/common.py`.

## Palette (tokens de `theme.py`) — monochrome
| token | valeur | usage |
|---|---|---|
| `BG` | `#030303` | fond fenêtre |
| `PANEL` / `PANEL_2` | `#0a0a0a` / `#111111` | cartes, champs |
| `LINE` / `LINE_2` | `#1f1f1f` / `#2c2c2c` | séparateurs, bordures |
| `FG` | `#ececec` | texte principal |
| `MUTED` | `#7d7d7d` | texte secondaire |
| `WHITE` | `#ffffff` | accents, sélection, valeurs fortes |
| `OK` / `WARN` / `DANGER` | `#d9ffe6` / `#ffe9b0` / `#ff9a9a` | sémantique **uniquement** |

**Interdits absolus** : dégradés violets, néon, couleurs vives décoratives, cartes
arrondies génériques partout, ombres portées marquées, look « template SaaS ».
Le blanc est le seul « accent ». Les couleurs OK/WARN/DANGER ne servent qu'à l'état
(succès/avertissement/erreur), jamais à décorer.

## Typographie
- **Titre display** : `widgets/pixel_title.PixelTitle` (police bitmap 5×7 en blocs,
  coulures animées). Pour le nom du produit et les grands titres d'écran d'accueil.
- **Interface** : `theme.ui_font_family()` (Segoe UI / system), fine, lettres espacées
  pour les libellés en MAJUSCULES (`letter-spacing`).
- **Données / technique** : `theme.mono_font_family()` (Cascadia/Consolas/DejaVu Mono)
  — journaux, IP, identifiants, chiffres alignés.
- Objets de style nommés (QSS) : `#H1`, `#H2`, `#Muted`, `#Mono`, `#Warn`, `#Danger`,
  `#Card`, `#Sidebar`, `#NavButton`, `#Primary`, `#Danger`.

## Mise en page
- Espace négatif généreux, cinématographique. Séparateurs **fins** (1px `LINE`).
- Bordures minimales ; la carte `#Card` (fond `PANEL`, 1px `LINE`, rayon 6) ne sert
  qu'à isoler un élément qui le mérite — pas chaque bloc.
- En-têtes de page via `ui/pages/common.Page(title, subtitle, help_key=…)`.
- Grilles/flex avec `gap`, jamais des marges par élément. Gouttière ≥ 16px.
- Indicateurs d'état techniques et discrets (points `●`, pastilles `pill`).

## Fonds et ambiance
- `widgets/dot_field.DotField` : trame de points scintillants + image d'accueil
  intégrée (proportions conservées). Fond très atténué dans le dashboard
  (`image_opacity≈0.10`), plus présent sur l'accueil.
- Emblème : `resources/images/emblem.png` (visage dot-matrix dans un réticule,
  **création originale** — ne jamais reproduire un masque/personnage connu).
- Effets lumineux **retenus** (halo léger sur le titre), transitions fluides et
  courtes (200–420 ms, `QEasingCurve.OutCubic`), jamais d'animation permanente qui
  distrait. Respecter un futur réglage « mouvement réduit ».

## Visualisations — monochromes, peintes main
- Jamais de lib de charts externe : tout au `QPainter`, cohérent avec le dot-matrix.
- Réutiliser `widgets/charts.py` : `ActivityDots` (histogramme en points),
  `BarList` (barres fines), `Histogram` (barres verticales). Le pic en `WHITE`,
  le reste en gris ; étiquettes en mono ; axes/labels lisibles.
- Un graphique doit répondre à une question ; pas de graphique « pour remplir ».

## Composition d'une nouvelle page (check-list)
1. Hériter de `common.Page`, titre court + sous-titre explicatif + `help_key`.
2. Travaux lourds en tâche de fond (`ui/workers.run_async`), jamais dans l'UI.
3. États **loading / empty / error** soignés ; aucune fausse donnée.
4. Enregistrer la page dans `main_window.NAV` et la grille `pages/overview.MODULES`.
5. Journaliser l'action réelle (`ctx.repo.log_history` + `ctx.log_event`).
6. Revue « directeur artistique » : la page appartient-elle à FACE ANALYSE ?
   hiérarchie claire, alignements précis, rien de superflu, premium sans surcharge.

## Rendu/vérification
- Qt hors écran pour les captures : `QT_QPA_PLATFORM=offscreen`, `FACE_ANALYSE_HOME`
  pointant un dossier jetable ; `window.grab().save(...)`.
- Toujours regarder le rendu (desktop) avant de considérer une page finie.
