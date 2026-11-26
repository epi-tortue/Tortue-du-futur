# Chauffer la batterie : combien ça coûte, combien ça rapporte ?

Départ 2026-01-01. Navigation parfaite, sans pannes (on isole l'effet thermique). Chaque ligne = moyenne sur un ensemble de largages décalés de 6 h (la trajectoire est chaotique : quelques Wh de différence font attraper ou rater une fenêtre météo). Gestion d'énergie S8 validée et S6 en place (verrou de charge < 0 °C). La batterie suit l'eau de mer (T_bat → SST + Δ) avec une constante de temps de ~2,8 h ; le chauffage (10 W max, consigne 6 °C) n'utilise que le surplus solaire (mode « quand_soleil ») ou tourne en permanence (« toujours »).

| Δ = T_bat − SST | Chauffage | Énergie chauffage | Énergie bloquée par le froid | Énergie écrêtée | Solaire utilisé | Moteur | Arrivées | Jour de fin (médiane) | Reste (nm, médiane) |
|---|---|---|---|---|---|---|---|---|---|
| +2 °C | non | 0 Wh | 0 Wh | 0 Wh | 8064 Wh | 6185 Wh | 8/8 | 42 | 13 |
| +2 °C | quand_soleil | 12 Wh | 0 Wh | 0 Wh | 8064 Wh | 6179 Wh | 8/8 | 42 | 13 |
| +2 °C | toujours | 75 Wh | 0 Wh | 0 Wh | 8072 Wh | 6135 Wh | 8/8 | 42 | 13 |
| +0 °C | non | 0 Wh | 0 Wh | 0 Wh | 8063 Wh | 6184 Wh | 8/8 | 42 | 13 |
| +0 °C | quand_soleil | 51 Wh | 0 Wh | 0 Wh | 8064 Wh | 6146 Wh | 8/8 | 42 | 13 |
| +0 °C | toujours | 269 Wh | 0 Wh | 0 Wh | 8095 Wh | 6062 Wh | 8/8 | 43 | 13 |
| -3 °C | non | 0 Wh | 85 Wh | 85 Wh | 7977 Wh | 6117 Wh | 8/8 | 42 | 13 |
| -3 °C | quand_soleil | 154 Wh | 0 Wh | 0 Wh | 8058 Wh | 6080 Wh | 8/8 | 42 | 13 |
| -3 °C | toujours | 344 Wh | 547 Wh | 547 Wh | 7822 Wh | 5779 Wh | 8/8 | 42 | 13 |
| -6 °C | non | 0 Wh | 657 Wh | 657 Wh | 7498 Wh | 5852 Wh | 8/8 | 43 | 13 |
| -6 °C | quand_soleil | 518 Wh | 4 Wh | 4 Wh | 7974 Wh | 5751 Wh | 8/8 | 43 | 13 |
| -6 °C | toujours | 1586 Wh | 1082 Wh | 7486 Wh | 81511 Wh | 65902 Wh | 4/8 | 26 | 88 |

## Verdict

- **Δ = +2 °C** : sans chauffage, 0 Wh refusés par le froid. Avec chauffage « quand_soleil » : 12 Wh dépensés, 0 Wh récupérés → bilan -12 Wh ; jour d'arrivée médian 42 → 42 (8 → 8 arrivées sur 8).
- **Δ = +0 °C** : sans chauffage, 0 Wh refusés par le froid. Avec chauffage « quand_soleil » : 51 Wh dépensés, 0 Wh récupérés → bilan -51 Wh ; jour d'arrivée médian 42 → 42 (8 → 8 arrivées sur 8).
- **Δ = -3 °C** : sans chauffage, 85 Wh refusés par le froid. Avec chauffage « quand_soleil » : 154 Wh dépensés, 85 Wh récupérés → bilan -69 Wh ; jour d'arrivée médian 42 → 42 (8 → 8 arrivées sur 8).
- **Δ = -6 °C** : sans chauffage, 657 Wh refusés par le froid. Avec chauffage « quand_soleil » : 518 Wh dépensés, 653 Wh récupérés → bilan +135 Wh ; jour d'arrivée médian 43 → 43 (8 → 8 arrivées sur 8).

Le surplus solaire de l'hiver est faible : avec la batterie couplée à l'eau (Δ ≥ 0), le froid ne bloque presque rien et le chauffage est une dépense pure. Il ne devient rentable que si la batterie est nettement plus froide que l'eau (Δ ≤ −3 °C), cas d'un compartiment couplé à l'air. Attention : l'issue est très sensible au calendrier d'arrivée (voir « piège des 100 derniers milles » dans le rapport) — un écart de jours peut venir d'une fenêtre météo attrapée ou manquée, pas de l'énergie elle-même.


Lecture : « énergie bloquée par le froid » = surplus solaire que le BMS refuse parce que la batterie est sous 5 °C (charge limitée à 0,1 C) ou sous 0 °C (charge interdite). Le chauffage n'a d'intérêt que si ce volume dépasse sa propre consommation. Δ = +2 °C est l'hypothèse par défaut (batterie au fond de coque, couplée à l'eau) ; Δ négatifs = batterie plus froide que l'eau (couplage à l'air, nuit, vent).