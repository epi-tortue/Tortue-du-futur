# Optimisations

Règle suivie : **résultats identiques au bit près**. La trajectoire est chaotique (un écart d'un bit sur une
vitesse finit par décaler un événement d'un pas de temps, donc l'issue de certaines missions) : une
approximation, même minuscule, rendrait impossible la comparaison des versions sur les mêmes graines. Chaque
optimisation est vérifiée par `tests/test_non_regression.py` (Monte-Carlo de référence, égalité des noyaux
compilés, du lot unique et du bootstrap).

Profilage : `cProfile` (`python main.py profil`) puis **py-spy** (échantillonnage). cProfile gonfle le coût des
petites fonctions appelées des centaines de milliers de fois et ne voit pas le temps passé dans les bibliothèques
C : il plaçait l'équilibre du bateau en tête (≈ 25 %), alors que py-spy a montré que l'estimateur Codac pesait
≈ 36 % du temps réel et l'équilibre ≈ 5 %.

Banc : 16 missions (8 configuration actuelle + 8 tout validé), un processus, grille 1°, minimum de 3 répétitions.

| Étape | Mesure | Gain |
|---|---|---|
| Point de départ de cette phase (après les premières optimisations de l'équilibre et de l'interpolation) | rapport complet estimé à 17,2 min (32 min à l'origine) ; banc 6,6 s | — |
| Équilibre du bateau compilé avec numba (`sim/noyaux.py`), `math.hypot` de CPython porté à l'identique | 22,6 → 2,7 µs par appel | ≈ 5 % du temps total (l'équilibre ne pesait que 5 %) |
| Estimateur Codac : bornes de la boîte gardées en flottants, intersection avec le fix GPS en max/min (exacte), centre et largeur calculés une fois par boîte | banc 6,6 → 5,45 s | −18 % |
| Risques (modulateurs précalculés, accès direct aux processus aléatoires), densités GFW en flottants Python, gestion d'énergie (mémo de la prévision horaire, `min/max` au lieu de `np.clip` scalaire) | banc 5,45 → 4,57 s | −16 % |
| Interpolation météo : bloc des 8 coins réutilisé tant que la cellule ne change pas, `tolist()` au lieu de 14 extractions de scalaires numpy | banc 4,57 → 4,24 s | −7 % |
| Monte-Carlo : trajectoire réduite aux 6 séries que le résumé lit | débit parallèle 6,7 → 7,6 runs/s (avec les lignes ci-dessus) | — |
| Rapport : un seul pool de processus pour les 5 Monte-Carlo, tâches longues en premier, runs identiques calculés une fois (400 sur 10 100) | 5 démarrages de pool → 1 ; −4 % de runs | ≈ −0,5 min |
| Bootstrap hiérarchique compilé (numba reproduit la suite aléatoire de numpy ; somme par paires de numpy reproduite) | 300 → 7 ms par intervalle, ≈ 300 intervalles par rapport | ≈ −1,5 min |
| Analyses physiques du rapport (chauffage : 96 missions ; cercle d'arrivée : 24) en parallèle | 34 s → 15 s (démarrage du pool compris) | ≈ −0,3 min |

Correction trouvée en chemin (H78) : `import codac` met le processeur en arrondi vers le haut. Ce n'est pas une
optimisation, mais c'est elle qui empêchait le noyau numba de coïncider avec Python, et elle rendait le premier
run de chaque processus différent des autres.

**Mesure finale** (`python main.py --start 2026-01-01 --runs 500`, 14 processus, grille 1°) : **8,2 min**
(Monte-Carlo 457 s, figures 6 s, histoire 5 s, récits 7 s, chauffage et cercles 15 s). Mesure intermédiaire,
après les optimisations de la simulation mais avant celles du rapport : 11,7 min.

Pistes écartées : interpolation compilée (le produit BLAS de numpy dépend de la disposition mémoire et
n'est pas reproductible par une boucle simple) ; pas de temps de 1 h au lieu de 30 min, ou moins d'appels
Codac sans fix GPS (approximations : on ne pourrait pas garantir l'écart de 0,5 point sur des trajectoires
chaotiques) ; 16 processus au lieu de 14 (plus lent : 8 cœurs physiques, l'hyperthreading sature).
