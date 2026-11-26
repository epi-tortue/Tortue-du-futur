# Mission du 2026-01-01 — histoire la plus probable (calculateur figé)

Run médian de l'issue la plus fréquente du Monte-Carlo (« calculateur figé », 28 % des 500 runs).

*Largage le 01/01/2026 12:30 UTC par 47.00°N 47.98°W. Solutions en place : S1=partielle. Graine 202611004, jeu de paramètres 11.*

> Scénario plausible rejoué sur la météo réelle 2026, **pas une prédiction** : pannes et rencontres sont tirées au hasard selon des taux incertains (voir HYPOTHESES.md).

## Jour 0 — 01/01/2026
- **Position** (midi) : 47.14°N 47.53°W — reste 1231 nm (gagné 41 nm dans la journée)
- **Météo** : vent moyen 5 m/s (rafales 8), vagues jusqu'à 3.2 m, courant 0.18 m/s, eau 2.2 °C, air 2 à 4 °C
- **Énergie** : solaire 76 Wh, moteur 436 Wh ; batterie 0–98 % à 4.1 °C
- **Navigation** : GPS disponible 90 % du temps ; boîte Codac jusqu'à 35.2 km ; vitesse fond moyenne 0.89 m/s
- **Autopilote** : route vers l'arrivée → mode dégradé (cap fixe ENE, puissance réduite) → black-out (batterie vide)
- 21:00 **[P18]** Perte du signal GPS pendant 2.4 h (47.11°N 47.69°W)
- ⚠️ 10:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°1, SOC accessible 0 %, batterie 4.6 °C) (47.29°N 47.09°W)

## Jour 1 — 02/01/2026
- **Position** (midi) : 47.39°N 46.89°W — reste 1224 nm (gagné 7 nm dans la journée)
- **Météo** : vent moyen 6 m/s (rafales 12), vagues jusqu'à 3.0 m, courant 0.15 m/s, eau 2.9 °C, air 3 à 5 °C
- **Énergie** : solaire 131 Wh, moteur 100 Wh ; batterie 0–14 % à 4.9 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 282.8 km ; vitesse fond moyenne 0.45 m/s
- **Autopilote** : black-out (batterie vide) → mode dégradé (cap fixe ENE, puissance réduite) → route vers l'arrivée
- 14:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°1) (47.30°N 47.09°W)
- ⚠️ 20:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°2, SOC accessible 0 %, batterie 4.9 °C) (47.35°N 46.89°W)

## Jour 2 — 03/01/2026
- **Position** (midi) : 47.40°N 46.51°W — reste 1195 nm (gagné 29 nm dans la journée)
- **Météo** : vent moyen 10 m/s (rafales 15), vagues jusqu'à 3.9 m, courant 0.20 m/s, eau 3.5 °C, air 2 à 6 °C
- **Énergie** : solaire 174 Wh, moteur 142 Wh ; batterie 0–19 % à 5.4 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 333.8 km ; vitesse fond moyenne 0.72 m/s
- **Autopilote** : black-out (batterie vide) → mode dégradé (cap fixe ENE, puissance réduite) → route vers l'arrivée
- 14:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°2) (47.31°N 46.95°W)
- ⚠️ 21:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°3, SOC accessible 0 %, batterie 5.3 °C) (47.39°N 46.60°W)

## Jour 3 — 04/01/2026
- **Position** (midi) : 47.63°N 45.59°W — reste 1167 nm (gagné 28 nm dans la journée)
- **Météo** : vent moyen 10 m/s (rafales 24), vagues jusqu'à 4.0 m, courant 0.20 m/s, eau 4.2 °C, air 3 à 10 °C
- **Énergie** : solaire 249 Wh, moteur 205 Wh ; batterie 0–30 % à 6.2 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 297.4 km ; vitesse fond moyenne 0.93 m/s
- **Autopilote** : black-out (batterie vide) → mode dégradé (cap fixe ENE, puissance réduite) → route vers l'arrivée
- 13:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°3) (47.46°N 46.19°W)
- ⚠️ 00:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°4, SOC accessible 0 %, batterie 6.3 °C) (47.62°N 45.59°W)

## Jour 4 — 05/01/2026
- **Position** (midi) : 48.11°N 45.39°W — reste 1132 nm (gagné 36 nm dans la journée)
- **Météo** : vent moyen 15 m/s (rafales 28), vagues jusqu'à 5.0 m, courant 0.29 m/s, eau 4.1 °C, air 1 à 10 °C
- **Énergie** : solaire 76 Wh, moteur 58 Wh ; batterie 0–12 % à 6.1 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 291.9 km ; vitesse fond moyenne 0.87 m/s
- **Autopilote** : black-out (batterie vide) → mode dégradé (cap fixe ENE, puissance réduite) → route vers l'arrivée → calculateur figé
- 15:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°4) (47.96°N 45.74°W)
- ⚠️ 19:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°5, SOC accessible 0 %, batterie 5.8 °C) (48.06°N 45.59°W)
- ⚠️ 19:30 **[P17]** Le calculateur se fige (bug temporel / saturation) et rien ne le redémarre : moteur et barre figés (48.07°N 45.57°W)
- ⚠️ 19:30 Fin de mission : calculateur figé (48.07°N 45.57°W)
- ⚠️ 19:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°6, SOC accessible 0 %, batterie 5.8 °C) (48.07°N 45.57°W)

## Jour 5 — 06/01/2026
- **Position** (midi) : 48.20°N 44.34°W — reste 1095 nm (gagné 37 nm dans la journée)
- **Météo** : vent moyen 10 m/s (rafales 18), vagues jusqu'à 4.7 m, courant 0.27 m/s, eau 5.1 °C, air 0 à 2 °C
- **Énergie** : solaire 127 Wh, moteur 105 Wh ; batterie 0–10 % à 7.0 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 333.8 km ; vitesse fond moyenne 0.85 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- 13:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°5) (48.22°N 44.94°W)
- ⚠️ 19:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°7, SOC accessible 0 %, batterie 6.8 °C) (48.19°N 44.49°W)

## Jour 6 — 07/01/2026
- **Position** (midi) : 48.19°N 43.37°W — reste 1064 nm (gagné 31 nm dans la journée)
- **Météo** : vent moyen 9 m/s (rafales 15), vagues jusqu'à 3.6 m, courant 0.26 m/s, eau 6.5 °C, air 2 à 7 °C
- **Énergie** : solaire 150 Wh, moteur 126 Wh ; batterie 0–14 % à 8.3 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 351.9 km ; vitesse fond moyenne 0.88 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- 14:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°6) (48.23°N 43.97°W)
- ⚠️ 20:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°8, SOC accessible 0 %, batterie 8.2 °C) (48.18°N 43.44°W)

## Jour 7 — 08/01/2026
- **Position** (midi) : 48.80°N 43.12°W — reste 1035 nm (gagné 29 nm dans la journée)
- **Météo** : vent moyen 13 m/s (rafales 22), vagues jusqu'à 4.6 m, courant 0.54 m/s, eau 7.9 °C, air 6 à 10 °C
- **Énergie** : solaire 69 Wh, moteur 52 Wh ; batterie 0–11 % à 9.7 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 351.9 km ; vitesse fond moyenne 1.03 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- 15:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°7) (48.51°N 43.29°W)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°9, SOC accessible 0 %, batterie 9.2 °C) (48.58°N 43.15°W)

## Jour 8 — 09/01/2026
- **Position** (midi) : 49.34°N 42.44°W — reste 1003 nm (gagné 32 nm dans la journée)
- **Météo** : vent moyen 11 m/s (rafales 19), vagues jusqu'à 4.7 m, courant 0.32 m/s, eau 9.1 °C, air 5 à 8 °C
- **Énergie** : solaire 91 Wh, moteur 74 Wh ; batterie 0–36 % à 11.1 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 379.2 km ; vitesse fond moyenne 0.75 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- 15:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°8) (49.21°N 42.86°W)
- ⚠️ 19:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°10, SOC accessible 0 %, batterie 11.1 °C) (49.26°N 42.58°W)
- ⚠️ 02:00 **[P11]** Stockage (batterie) : défaillance de cellule, capacité ramenée à 5 % (49.35°N 42.40°W)
- 02:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°9) (49.35°N 42.40°W)
- ⚠️ 02:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°11, SOC accessible 0 %, batterie 11.2 °C) (49.35°N 42.39°W)
- 12:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°10) (49.33°N 42.17°W)

## Jour 9 — 10/01/2026
- **Position** (midi) : 49.21°N 41.76°W — reste 982 nm (gagné 21 nm dans la journée)
- **Météo** : vent moyen 10 m/s (rafales 21), vagues jusqu'à 4.9 m, courant 0.21 m/s, eau 10.1 °C, air 5 à 8 °C
- **Énergie** : solaire 90 Wh, moteur 32 Wh ; batterie 0–37 % à 11.9 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 291.9 km ; vitesse fond moyenne 0.59 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- ⚠️ 12:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°12, SOC accessible 0 %, batterie 11.2 °C) (49.33°N 42.16°W)
- 13:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°11) (49.32°N 42.15°W)
- ⚠️ 13:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°13, SOC accessible 0 %, batterie 11.2 °C) (49.31°N 42.13°W)
- 14:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°12) (49.31°N 42.12°W)
- ⚠️ 15:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°14, SOC accessible 0 %, batterie 11.3 °C) (49.29°N 42.07°W)
- 15:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°13) (49.28°N 42.06°W)
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°15, SOC accessible 0 %, batterie 11.4 °C) (49.25°N 41.96°W)
- 17:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°14) (49.24°N 41.95°W)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°16, SOC accessible 0 %, batterie 11.5 °C) (49.24°N 41.94°W)
- 19:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°15) (49.23°N 41.91°W)
- ⚠️ 19:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°17, SOC accessible 0 %, batterie 11.6 °C) (49.22°N 41.89°W)
- 11:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°16) (49.30°N 41.59°W)
- ⚠️ 12:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°18, SOC accessible 0 %, batterie 12.6 °C) (49.31°N 41.59°W)

## Jour 10 — 11/01/2026
- **Position** (midi) : 49.28°N 41.43°W — reste 966 nm (gagné 16 nm dans la journée)
- **Météo** : vent moyen 7 m/s (rafales 12), vagues jusqu'à 4.6 m, courant 0.20 m/s, eau 11.1 °C, air 6 à 8 °C
- **Énergie** : solaire 98 Wh, moteur 32 Wh ; batterie 0–42 % à 13.0 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 310.1 km ; vitesse fond moyenne 0.40 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- 12:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°17) (49.31°N 41.59°W)
- ⚠️ 13:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°19, SOC accessible 0 %, batterie 12.6 °C) (49.31°N 41.59°W)
- 13:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°18) (49.31°N 41.59°W)
- ⚠️ 14:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°20, SOC accessible 0 %, batterie 12.6 °C) (49.31°N 41.57°W)
- 15:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°19) (49.31°N 41.57°W)
- 15:30 **[P18]** Début d'une dérive lente du compas (biais) (49.31°N 41.57°W)
- ⚠️ 16:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°21, SOC accessible 0 %, batterie 12.7 °C) (49.30°N 41.55°W)
- 16:00 **[P18]** Panne du compas (valeur figée à 304°) (49.30°N 41.55°W)
- 16:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°20) (49.30°N 41.55°W)
- ⚠️ 17:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°22, SOC accessible 0 %, batterie 12.7 °C) (49.29°N 41.52°W)
- 18:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°21) (49.29°N 41.52°W)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°23, SOC accessible 0 %, batterie 12.8 °C) (49.29°N 41.52°W)
- 11:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°22) (49.29°N 41.17°W)
- ⚠️ 12:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°24, SOC accessible 0 %, batterie 13.4 °C) (49.29°N 41.16°W)

## Jour 11 — 12/01/2026
- **Position** (midi) : 49.60°N 40.92°W — reste 922 nm (gagné 45 nm dans la journée)
- **Météo** : vent moyen 17 m/s (rafales 38), vagues jusqu'à 11.2 m, courant 0.53 m/s, eau 11.8 °C, air 5 à 13 °C
- **Énergie** : solaire 67 Wh, moteur 21 Wh ; batterie 0–28 % à 13.8 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 315.6 km ; vitesse fond moyenne 1.14 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- 12:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°23) (49.30°N 41.15°W)
- ⚠️ 13:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°25, SOC accessible 0 %, batterie 13.5 °C) (49.30°N 41.11°W)
- 14:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°24) (49.31°N 41.10°W)
- ⚠️ 15:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°26, SOC accessible 0 %, batterie 13.5 °C) (49.32°N 41.05°W)
- 15:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°25) (49.33°N 41.05°W)
- ⚠️ 16:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°27, SOC accessible 0 %, batterie 13.6 °C) (49.34°N 41.04°W)
- 16:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°26) (49.35°N 41.04°W)
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°28, SOC accessible 0 %, batterie 13.6 °C) (49.37°N 41.03°W)
- 18:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°27) (49.39°N 41.03°W)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°29, SOC accessible 0 %, batterie 13.6 °C) (49.41°N 41.02°W)
- 11:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°28) (49.84°N 40.27°W)

## Jour 12 — 13/01/2026
- **Position** (midi) : 49.87°N 39.29°W — reste 859 nm (gagné 63 nm dans la journée)
- **Météo** : vent moyen 21 m/s (rafales 39), vagues jusqu'à 12.9 m, courant 0.72 m/s, eau 9.7 °C, air 5 à 6 °C
- **Énergie** : solaire 204 Wh, moteur 126 Wh ; batterie 0–100 % à 12.0 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 315.6 km ; vitesse fond moyenne 1.42 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 12:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°30, SOC accessible 0 %, batterie 13.5 °C) (49.86°N 40.20°W)
- 13:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°29) (49.86°N 40.16°W)
- ⚠️ 19:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°31, SOC accessible 0 %, batterie 12.5 °C) (49.90°N 39.70°W)
- 11:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°30) (49.87°N 38.57°W)

## Jour 13 — 14/01/2026
- **Position** (midi) : 49.78°N 37.62°W — reste 808 nm (gagné 51 nm dans la journée)
- **Météo** : vent moyen 17 m/s (rafales 26), vagues jusqu'à 8.7 m, courant 0.40 m/s, eau 8.9 °C, air 5 à 6 °C
- **Énergie** : solaire 216 Wh, moteur 147 Wh ; batterie 0–100 % à 10.9 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 306.5 km ; vitesse fond moyenne 1.25 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 13:00 **[P17]** Le calculateur se fige (bug temporel / saturation) et rien ne le redémarre : moteur et barre figés (49.86°N 38.45°W)
- ⚠️ 19:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°32, SOC accessible 0 %, batterie 10.6 °C) (49.82°N 37.90°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°31) (49.67°N 37.12°W)
- ⚠️ 11:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°33, SOC accessible 0 %, batterie 11.5 °C) (49.67°N 37.10°W)
- 12:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°32) (49.67°N 37.08°W)

## Jour 14 — 15/01/2026
- **Position** (midi) : 49.58°N 36.49°W — reste 774 nm (gagné 35 nm dans la journée)
- **Météo** : vent moyen 9 m/s (rafales 19), vagues jusqu'à 5.6 m, courant 0.35 m/s, eau 10.8 °C, air 7 à 12 °C
- **Énergie** : solaire 117 Wh, moteur 74 Wh ; batterie 0–31 % à 12.6 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 319.2 km ; vitesse fond moyenne 0.84 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- ⚠️ 16:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°34, SOC accessible 0 %, batterie 12.0 °C) (49.60°N 36.74°W)
- ⚠️ 16:30 **[P20]** Disqualifié : plus de 10 jours consécutifs (ou 15 cumulés) sans position transmise (règle B1) (49.59°N 36.72°W)
- 16:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°33) (49.59°N 36.72°W)
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°35, SOC accessible 0 %, batterie 12.2 °C) (49.59°N 36.70°W)
- 17:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°34) (49.59°N 36.69°W)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°36, SOC accessible 0 %, batterie 12.3 °C) (49.59°N 36.67°W)
- 12:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°35) (49.72°N 36.16°W)

## Jour 15 — 16/01/2026
- **Position** (midi) : 49.88°N 35.78°W — reste 742 nm (gagné 32 nm dans la journée)
- **Météo** : vent moyen 13 m/s (rafales 20), vagues jusqu'à 4.1 m, courant 0.30 m/s, eau 10.7 °C, air 11 à 12 °C
- **Énergie** : solaire 42 Wh, moteur 0 Wh ; batterie 0–18 % à 12.8 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 333.8 km ; vitesse fond moyenne 0.77 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- ⚠️ 12:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°37, SOC accessible 0 %, batterie 13.1 °C) (49.73°N 36.14°W)
- 13:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°36) (49.74°N 36.12°W)
- ⚠️ 13:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°38, SOC accessible 0 %, batterie 13.1 °C) (49.75°N 36.11°W)
- 14:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°37) (49.75°N 36.09°W)
- ⚠️ 14:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°39, SOC accessible 0 %, batterie 13.1 °C) (49.76°N 36.07°W)
- 15:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°38) (49.76°N 36.05°W)
- ⚠️ 15:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°40, SOC accessible 0 %, batterie 13.1 °C) (49.77°N 36.03°W)
- 16:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°39) (49.78°N 36.02°W)
- ⚠️ 16:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°41, SOC accessible 0 %, batterie 13.1 °C) (49.78°N 36.00°W)
- 17:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°40) (49.79°N 35.97°W)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°42, SOC accessible 0 %, batterie 13.1 °C) (49.79°N 35.95°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°41) (50.10°N 35.52°W)
- ⚠️ 11:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°43, SOC accessible 0 %, batterie 12.1 °C) (50.11°N 35.50°W)
- 12:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°42) (50.12°N 35.49°W)

## Jour 16 — 17/01/2026
- **Position** (midi) : 50.21°N 34.71°W — reste 686 nm (gagné 56 nm dans la journée)
- **Météo** : vent moyen 18 m/s (rafales 28), vagues jusqu'à 9.2 m, courant 0.48 m/s, eau 9.5 °C, air 5 à 12 °C
- **Énergie** : solaire 112 Wh, moteur 52 Wh ; batterie 0–32 % à 11.6 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 315.6 km ; vitesse fond moyenne 1.23 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- ⚠️ 12:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°44, SOC accessible 0 %, batterie 12.1 °C) (50.13°N 35.47°W)
- 13:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°43) (50.14°N 35.45°W)
- ⚠️ 13:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°45, SOC accessible 0 %, batterie 12.1 °C) (50.15°N 35.43°W)
- 14:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°44) (50.15°N 35.41°W)
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°46, SOC accessible 0 %, batterie 11.8 °C) (50.17°N 35.15°W)
- 17:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°45) (50.17°N 35.12°W)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°47, SOC accessible 0 %, batterie 11.8 °C) (50.18°N 35.09°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°46) (50.23°N 34.08°W)
- ⚠️ 11:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°48, SOC accessible 0 %, batterie 11.2 °C) (50.24°N 34.05°W)
- 12:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°47) (50.24°N 34.02°W)

## Jour 17 — 18/01/2026
- **Position** (midi) : 50.26°N 33.16°W — reste 638 nm (gagné 48 nm dans la journée)
- **Météo** : vent moyen 14 m/s (rafales 26), vagues jusqu'à 9.3 m, courant 0.41 m/s, eau 9.6 °C, air 6 à 8 °C
- **Énergie** : solaire 188 Wh, moteur 126 Wh ; batterie 0–100 % à 11.6 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 306.5 km ; vitesse fond moyenne 1.07 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°49, SOC accessible 0 %, batterie 11.4 °C) (50.22°N 33.45°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°48) (50.25°N 32.76°W)
- ⚠️ 11:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°50, SOC accessible 0 %, batterie 11.8 °C) (50.25°N 32.75°W)
- 12:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°49) (50.25°N 32.73°W)

## Jour 18 — 19/01/2026
- **Position** (midi) : 50.12°N 32.29°W — reste 615 nm (gagné 23 nm dans la journée)
- **Météo** : vent moyen 10 m/s (rafales 22), vagues jusqu'à 6.1 m, courant 0.28 m/s, eau 9.9 °C, air 5 à 11 °C
- **Énergie** : solaire 130 Wh, moteur 84 Wh ; batterie 0–31 % à 11.9 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 315.6 km ; vitesse fond moyenne 0.76 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- ⚠️ 12:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°51, SOC accessible 0 %, batterie 11.9 °C) (50.24°N 32.71°W)
- 13:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°50) (50.24°N 32.70°W)
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°52, SOC accessible 0 %, batterie 11.9 °C) (50.17°N 32.41°W)
- 17:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°51) (50.17°N 32.39°W)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°53, SOC accessible 0 %, batterie 11.9 °C) (50.16°N 32.38°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°52) (50.27°N 32.21°W)
- ⚠️ 12:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°54, SOC accessible 0 %, batterie 12.0 °C) (50.27°N 32.13°W)

## Jour 19 — 20/01/2026
- **Position** (midi) : 50.07°N 31.34°W — reste 581 nm (gagné 34 nm dans la journée)
- **Météo** : vent moyen 15 m/s (rafales 28), vagues jusqu'à 9.0 m, courant 0.38 m/s, eau 9.6 °C, air 6 à 9 °C
- **Énergie** : solaire 139 Wh, moteur 84 Wh ; batterie 0–37 % à 11.7 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 306.5 km ; vitesse fond moyenne 1.07 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- 12:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°53) (50.27°N 32.10°W)
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°55, SOC accessible 0 %, batterie 11.9 °C) (50.22°N 31.64°W)
- 17:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°54) (50.22°N 31.61°W)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°56, SOC accessible 0 %, batterie 11.9 °C) (50.22°N 31.59°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°55) (49.91°N 31.06°W)
- ⚠️ 11:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°57, SOC accessible 0 %, batterie 11.4 °C) (49.91°N 31.05°W)
- 11:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°56) (49.91°N 31.04°W)

## Jour 20 — 21/01/2026
- **Position** (midi) : 49.95°N 30.41°W — reste 539 nm (gagné 42 nm dans la journée)
- **Météo** : vent moyen 13 m/s (rafales 27), vagues jusqu'à 6.6 m, courant 0.25 m/s, eau 9.7 °C, air 3 à 9 °C
- **Énergie** : solaire 177 Wh, moteur 147 Wh ; batterie 0–100 % à 11.6 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 306.5 km ; vitesse fond moyenne 0.99 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°58, SOC accessible 0 %, batterie 11.6 °C) (49.86°N 30.56°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°57) (49.95°N 30.00°W)

## Jour 21 — 22/01/2026
- **Position** (midi) : 49.78°N 29.14°W — reste 501 nm (gagné 38 nm dans la journée)
- **Météo** : vent moyen 15 m/s (rafales 26), vagues jusqu'à 9.4 m, courant 0.32 m/s, eau 10.5 °C, air 3 à 6 °C
- **Énergie** : solaire 251 Wh, moteur 158 Wh ; batterie 0–100 % à 12.4 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 297.4 km ; vitesse fond moyenne 1.13 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°59, SOC accessible 0 %, batterie 12.3 °C) (49.83°N 29.36°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°58) (49.64°N 28.74°W)

## Jour 22 — 23/01/2026
- **Position** (midi) : 49.54°N 28.02°W — reste 455 nm (gagné 46 nm dans la journée)
- **Météo** : vent moyen 16 m/s (rafales 30), vagues jusqu'à 9.0 m, courant 0.44 m/s, eau 10.3 °C, air 6 à 10 °C
- **Énergie** : solaire 298 Wh, moteur 158 Wh ; batterie 0–100 % à 12.3 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 297.4 km ; vitesse fond moyenne 1.21 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°60, SOC accessible 0 %, batterie 12.4 °C) (49.47°N 28.19°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°59) (49.53°N 27.44°W)

## Jour 23 — 24/01/2026
- **Position** (midi) : 49.33°N 26.54°W — reste 424 nm (gagné 30 nm dans la journée)
- **Météo** : vent moyen 13 m/s (rafales 29), vagues jusqu'à 9.1 m, courant 0.37 m/s, eau 10.7 °C, air 7 à 10 °C
- **Énergie** : solaire 258 Wh, moteur 136 Wh ; batterie 0–100 % à 12.7 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 306.5 km ; vitesse fond moyenne 1.05 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°61, SOC accessible 0 %, batterie 12.6 °C) (49.38°N 26.74°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°60) (49.56°N 26.52°W)
- ⚠️ 11:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°62, SOC accessible 0 %, batterie 12.6 °C) (49.57°N 26.52°W)
- 12:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°61) (49.59°N 26.52°W)

## Jour 24 — 25/01/2026
- **Position** (midi) : 49.70°N 25.83°W — reste 378 nm (gagné 46 nm dans la journée)
- **Météo** : vent moyen 14 m/s (rafales 25), vagues jusqu'à 8.3 m, courant 0.35 m/s, eau 10.5 °C, air 4 à 10 °C
- **Énergie** : solaire 186 Wh, moteur 116 Wh ; batterie 0–100 % à 12.6 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 288.3 km ; vitesse fond moyenne 1.02 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- ⚠️ 12:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°63, SOC accessible 0 %, batterie 12.6 °C) (49.60°N 26.51°W)
- 13:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°62) (49.61°N 26.50°W)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°64, SOC accessible 0 %, batterie 12.6 °C) (49.64°N 26.07°W)
- 10:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°63) (49.80°N 25.45°W)
- ⚠️ 10:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°65, SOC accessible 0 %, batterie 12.5 °C) (49.81°N 25.44°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°64) (49.81°N 25.42°W)

## Jour 25 — 26/01/2026
- **Position** (midi) : 49.91°N 24.73°W — reste 335 nm (gagné 43 nm dans la journée)
- **Météo** : vent moyen 10 m/s (rafales 20), vagues jusqu'à 9.0 m, courant 0.47 m/s, eau 10.5 °C, air 4 à 7 °C
- **Énergie** : solaire 294 Wh, moteur 147 Wh ; batterie 0–100 % à 12.5 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 288.3 km ; vitesse fond moyenne 0.97 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°66, SOC accessible 0 %, batterie 12.5 °C) (49.84°N 24.95°W)
- 10:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°65) (50.07°N 24.42°W)
- ⚠️ 10:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°67, SOC accessible 0 %, batterie 12.4 °C) (50.08°N 24.40°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°66) (50.09°N 24.39°W)

## Jour 26 — 27/01/2026
- **Position** (midi) : 50.02°N 23.86°W — reste 313 nm (gagné 22 nm dans la journée)
- **Météo** : vent moyen 8 m/s (rafales 17), vagues jusqu'à 7.9 m, courant 0.26 m/s, eau 10.7 °C, air 6 à 9 °C
- **Énergie** : solaire 264 Wh, moteur 136 Wh ; batterie 0–100 % à 12.6 °C
- **Navigation** : GPS disponible 90 % du temps ; boîte Codac jusqu'à 297.4 km ; vitesse fond moyenne 0.71 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°68, SOC accessible 0 %, batterie 12.6 °C) (50.08°N 24.00°W)
- 22:00 **[P18]** Perte du signal GPS pendant 2.0 h (50.06°N 23.93°W)
- 10:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°67) (49.93°N 23.66°W)
- ⚠️ 10:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°69, SOC accessible 0 %, batterie 12.8 °C) (49.93°N 23.65°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°68) (49.93°N 23.64°W)

## Jour 27 — 28/01/2026
- **Position** (midi) : 50.09°N 23.09°W — reste 276 nm (gagné 36 nm dans la journée)
- **Météo** : vent moyen 12 m/s (rafales 21), vagues jusqu'à 8.9 m, courant 0.33 m/s, eau 10.7 °C, air 8 à 10 °C
- **Énergie** : solaire 175 Wh, moteur 126 Wh ; batterie 0–100 % à 12.7 °C
- **Navigation** : GPS disponible 96 % du temps ; boîte Codac jusqu'à 306.5 km ; vitesse fond moyenne 0.91 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- 14:30 **[P18]** Perte du signal GPS pendant 0.8 h (49.93°N 23.42°W)
- ⚠️ 15:30 **[P17]** Le calculateur se fige (bug temporel / saturation) et rien ne le redémarre : moteur et barre figés (49.94°N 23.35°W)
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°70, SOC accessible 0 %, batterie 12.7 °C) (49.95°N 23.26°W)
- 09:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°69) (50.15°N 22.80°W)
- ⚠️ 10:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°71, SOC accessible 0 %, batterie 12.6 °C) (50.14°N 22.78°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°70) (50.13°N 22.76°W)

## Jour 28 — 29/01/2026
- **Position** (midi) : 50.05°N 21.99°W — reste 238 nm (gagné 38 nm dans la journée)
- **Météo** : vent moyen 16 m/s (rafales 28), vagues jusqu'à 9.3 m, courant 0.37 m/s, eau 10.9 °C, air 7 à 9 °C
- **Énergie** : solaire 251 Wh, moteur 136 Wh ; batterie 0–100 % à 12.8 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 297.4 km ; vitesse fond moyenne 1.06 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°72, SOC accessible 0 %, batterie 12.7 °C) (50.07°N 22.26°W)
- 10:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°71) (50.00°N 21.55°W)
- ⚠️ 10:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°73, SOC accessible 0 %, batterie 13.2 °C) (49.99°N 21.52°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°72) (49.99°N 21.50°W)

## Jour 29 — 30/01/2026
- **Position** (midi) : 49.73°N 20.59°W — reste 207 nm (gagné 31 nm dans la journée)
- **Météo** : vent moyen 15 m/s (rafales 28), vagues jusqu'à 8.0 m, courant 0.31 m/s, eau 11.9 °C, air 8 à 11 °C
- **Énergie** : solaire 207 Wh, moteur 136 Wh ; batterie 0–100 % à 13.9 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 297.4 km ; vitesse fond moyenne 1.10 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°74, SOC accessible 0 %, batterie 14.0 °C) (49.79°N 20.86°W)
- 10:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°73) (49.82°N 20.35°W)
- ⚠️ 10:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°75, SOC accessible 0 %, batterie 13.9 °C) (49.82°N 20.33°W)
- 11:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°74) (49.82°N 20.31°W)

## Jour 30 — 31/01/2026
- **Position** (midi) : 49.79°N 19.40°W — reste 170 nm (gagné 37 nm dans la journée)
- **Météo** : vent moyen 13 m/s (rafales 22), vagues jusqu'à 6.4 m, courant 0.35 m/s, eau 11.6 °C, air 9 à 11 °C
- **Énergie** : solaire 256 Wh, moteur 126 Wh ; batterie 0–100 % à 13.6 °C
- **Navigation** : GPS disponible 65 % du temps ; boîte Codac jusqu'à 288.3 km ; vitesse fond moyenne 1.10 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°76, SOC accessible 0 %, batterie 13.7 °C) (49.77°N 19.64°W)
- 23:00 **[P18]** Perte du signal GPS pendant 8.1 h (49.78°N 19.45°W)
- 09:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°75) (49.99°N 19.26°W)
- ⚠️ 10:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°77, SOC accessible 0 %, batterie 13.5 °C) (50.01°N 19.26°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°76) (50.02°N 19.26°W)
- ⚠️ 11:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°78, SOC accessible 0 %, batterie 13.5 °C) (50.04°N 19.27°W)
- 11:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°77) (50.05°N 19.27°W)
- ⚠️ 12:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°79, SOC accessible 0 %, batterie 13.5 °C) (50.07°N 19.28°W)

## Jour 31 — 01/02/2026
- **Position** (midi) : 50.34°N 19.37°W — reste 155 nm (gagné 15 nm dans la journée)
- **Météo** : vent moyen 12 m/s (rafales 22), vagues jusqu'à 6.5 m, courant 0.26 m/s, eau 11.5 °C, air 8 à 11 °C
- **Énergie** : solaire 125 Wh, moteur 42 Wh ; batterie 0–80 % à 13.4 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 306.5 km ; vitesse fond moyenne 0.74 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- 12:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°78) (50.08°N 19.28°W)
- ⚠️ 13:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°80, SOC accessible 0 %, batterie 13.5 °C) (50.11°N 19.27°W)
- 14:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°79) (50.13°N 19.28°W)
- ⚠️ 15:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°81, SOC accessible 0 %, batterie 13.5 °C) (50.15°N 19.27°W)
- 15:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°80) (50.17°N 19.27°W)
- ⚠️ 16:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°82, SOC accessible 0 %, batterie 13.5 °C) (50.18°N 19.28°W)
- 16:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°81) (50.20°N 19.29°W)
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°83, SOC accessible 0 %, batterie 13.5 °C) (50.21°N 19.30°W)
- 09:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°82) (50.24°N 19.11°W)
- ⚠️ 10:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°84, SOC accessible 0 %, batterie 13.5 °C) (50.24°N 19.09°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°83) (50.24°N 19.08°W)

## Jour 32 — 02/02/2026
- **Position** (midi) : 50.25°N 18.37°W — reste 123 nm (gagné 32 nm dans la journée)
- **Météo** : vent moyen 9 m/s (rafales 14), vagues jusqu'à 6.4 m, courant 0.28 m/s, eau 11.9 °C, air 9 à 10 °C
- **Énergie** : solaire 261 Wh, moteur 147 Wh ; batterie 0–100 % à 13.9 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 288.3 km ; vitesse fond moyenne 0.86 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°85, SOC accessible 0 %, batterie 13.8 °C) (50.20°N 18.52°W)
- 09:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°84) (50.37°N 18.14°W)
- ⚠️ 10:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°86, SOC accessible 0 %, batterie 14.0 °C) (50.38°N 18.13°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°85) (50.38°N 18.12°W)

## Jour 33 — 03/02/2026
- **Position** (midi) : 50.47°N 17.61°W — reste 106 nm (gagné 18 nm dans la journée)
- **Météo** : vent moyen 8 m/s (rafales 16), vagues jusqu'à 5.4 m, courant 0.26 m/s, eau 12.0 °C, air 9 à 10 °C
- **Énergie** : solaire 245 Wh, moteur 147 Wh ; batterie 0–100 % à 14.0 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 288.3 km ; vitesse fond moyenne 0.74 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°87, SOC accessible 0 %, batterie 14.1 °C) (50.40°N 17.61°W)
- 09:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°86) (50.61°N 17.78°W)
- ⚠️ 10:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°88, SOC accessible 0 %, batterie 13.7 °C) (50.62°N 17.80°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°87) (50.63°N 17.81°W)

## Jour 34 — 04/02/2026
- **Position** (midi) : 50.68°N 17.86°W — reste 107 nm (perdu 2 nm dans la journée)
- **Météo** : vent moyen 10 m/s (rafales 16), vagues jusqu'à 5.3 m, courant 0.29 m/s, eau 11.5 °C, air 10 à 11 °C
- **Énergie** : solaire 210 Wh, moteur 126 Wh ; batterie 0–100 % à 13.6 °C
- **Navigation** : GPS disponible 92 % du temps ; boîte Codac jusqu'à 297.4 km ; vitesse fond moyenne 0.57 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 17:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°89, SOC accessible 0 %, batterie 13.7 °C) (50.64°N 17.66°W)
- 07:30 **[P18]** Perte du signal GPS pendant 1.6 h (50.76°N 18.01°W)
- 09:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°88) (50.78°N 18.06°W)
- ⚠️ 10:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°90, SOC accessible 0 %, batterie 13.3 °C) (50.79°N 18.08°W)
- 10:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°89) (50.79°N 18.09°W)
- ⚠️ 11:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°91, SOC accessible 0 %, batterie 13.3 °C) (50.79°N 18.09°W)
- 12:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°90) (50.79°N 18.11°W)

## Jour 35 — 05/02/2026
- **Position** (midi) : 50.74°N 18.23°W — reste 113 nm (perdu 5 nm dans la journée)
- **Météo** : vent moyen 9 m/s (rafales 15), vagues jusqu'à 5.2 m, courant 0.17 m/s, eau 11.2 °C, air 10 à 11 °C
- **Énergie** : solaire 187 Wh, moteur 136 Wh ; batterie 0–73 % à 13.2 °C
- **Navigation** : GPS disponible 79 % du temps ; boîte Codac jusqu'à 279.2 km ; vitesse fond moyenne 0.43 m/s
- **Autopilote** : black-out (batterie vide) → calculateur figé
- ⚠️ 17:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°92, SOC accessible 0 %, batterie 13.2 °C) (50.76°N 18.08°W)
- 18:00 **[P12]** Batterie rechargée : redémarrage du calculateur (n°91) (50.76°N 18.10°W)
- ⚠️ 18:30 **[P12]** Batterie vide : le BMS coupe tout (black-out n°93, SOC accessible 0 %, batterie 13.3 °C) (50.76°N 18.12°W)
- 02:00 **[P18]** Perte du signal GPS pendant 4.6 h (50.73°N 18.25°W)
- 09:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°92) (50.69°N 18.24°W)

## Jour 36 — 06/02/2026
- **Position** (midi) : 50.58°N 17.47°W — reste 90 nm (gagné 22 nm dans la journée)
- **Météo** : vent moyen 8 m/s (rafales 12), vagues jusqu'à 4.1 m, courant 0.20 m/s, eau 11.8 °C, air 10 à 10 °C
- **Énergie** : solaire 285 Wh, moteur 168 Wh ; batterie 0–100 % à 13.8 °C
- **Navigation** : GPS disponible 100 % du temps ; boîte Codac jusqu'à 288.3 km ; vitesse fond moyenne 0.87 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°94, SOC accessible 0 %, batterie 13.7 °C) (50.56°N 17.62°W)
- 09:30 **[P12]** Batterie rechargée : redémarrage du calculateur (n°93) (50.66°N 17.25°W)

## Jour 37 — 07/02/2026
- **Position** (midi) : 50.61°N 16.49°W — reste 83 nm (gagné 7 nm dans la journée)
- **Météo** : vent moyen 6 m/s (rafales 10), vagues jusqu'à 3.3 m, courant 0.18 m/s, eau 11.9 °C, air 10 à 11 °C
- **Énergie** : solaire 225 Wh, moteur 126 Wh ; batterie 0–100 % à 13.9 °C
- **Navigation** : GPS disponible 95 % du temps ; boîte Codac jusqu'à 264.6 km ; vitesse fond moyenne 0.74 m/s
- **Autopilote** : calculateur figé → black-out (batterie vide)
- 13:30 **[P24]** Pris dans un engin de pêche, le bateau finit par se libérer (50.65°N 16.97°W)
- ⚠️ 18:00 **[P12]** Batterie vide : le BMS coupe tout (black-out n°95, SOC accessible 0 %, batterie 14.0 °C) (50.61°N 16.62°W)
- 23:30 **[P18]** Perte du signal GPS pendant 1.0 h (50.61°N 16.51°W)
- ⚠️ 09:00 Pris dans un filet / une palangre et remonté à bord par le pêcheur (50.62°N 16.31°W)

## Fin de l'histoire

- **Fin de mission** : calculateur figé, jour 4.3 (05/01/2026 19:30) (cause : P17)
- **Devenir du bateau** : à bord d'un navire de pêche ; dernière position 50.62°N 16.31°W le 08/02/2026 09:00 ; position connue (télémétrie, balise ou récupération)
- **Bilan** : 1587 nm parcourus ; solaire 6.7 kWh, moteur 5.5 kWh, électronique 1.0 kWh ; 95 black-out(s), 93 redémarrage(s) ; 0 fix GPS rejetés pour 14 sauts injectés
- **Problèmes rencontrés** : P9×1, P12×5, P17×1