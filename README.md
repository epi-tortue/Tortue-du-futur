# Simulateur de mission Epi'Tortue

*« Si on avait lancé le bateau le 1er janvier 2026, que lui serait-il probablement arrivé ? »*

Le simulateur rejoue la **météo, les vagues, les courants et la pêche réels** (2026, et 2024–2025 pour comparer),
y plonge un modèle du bateau (coque finale [Testa](https://github.com/epi-tortue/Testa), énergie solaire, batterie,
autopilote, estimateur **Codac**) avec les **28 problèmes P1–P28** de la [doc](https://epi-tortue.github.io/docs/),
puis produit une histoire (journal de bord, carte) et une statistique d'issues (Monte-Carlo). C'est un scénario
plausible, **pas une prédiction** : chaque probabilité est donnée avec un intervalle à 90 %, et toutes les
hypothèses chiffrées sont dans [HYPOTHESES.md](HYPOTHESES.md).

## Installation

```bash
pip install numpy scipy pandas matplotlib pyyaml requests shapely pvlib folium codac gfw-api-python-client pytest
pip install numba        # facultatif mais conseillé : noyau de l'équilibre du bateau compilé (résultats identiques)
pip install streamlit    # facultatif : interface graphique
```

Le jeton Global Fishing Watch se met dans `secrets.yaml` (`gfw_api_access_token: "..."`) ou dans la variable
d'environnement `GFW_API_ACCESS_TOKEN`. Ce fichier est ignoré par git ; l'interface ne l'affiche ni ne le copie.

Sans numba, le même code tourne en Python pur, avec les mêmes résultats au bit près (environ 5 % plus lent).
Pour forcer ce mode : `EPITORTUE_SANS_NUMBA=1`.

## Utilisation

```bash
python main.py donnees                 # télécharge et met en cache (reprenable ; ensuite hors ligne)
python main.py donnees --fine          # + couloir à 1° (plusieurs jours de quota Open-Meteo)
python main.py donnees --annees        # + années de donnees.annees (2024, 2025) pour séparer météo et modèle
python main.py etat                    # ce qui est en cache, ce qui manque, grille utilisée
python main.py controle                # figure de contrôle : vent, vagues, courants, pêche au 01/01/2026
python main.py --start 2026-01-01 --runs 500     # rapport complet -> out/rapport_20260101.md (≈ 8 min)
python main.py histoire --start 2026-01-01       # mode histoire interactif
python main.py simuler --graine 7                # une mission : carte HTML, courbes, journal de bord
python main.py chauffage                         # chauffer la batterie : coût et gain
python main.py montecarlo --runs 500             # issues seules
python main.py calibration                       # contrôle : tout « partiel » ≈ historique Microtransat
python main.py effets                            # effet de chaque correction du modèle, mêmes graines
python main.py annees --runs 200                 # même départ en 2024, 2025, 2026 : météo contre modèle
python main.py peche --runs 200                  # captures : route de la mission contre route côtière
python main.py profil                            # cProfile d'une mission et d'un petit Monte-Carlo
python -m pytest                                 # tests (physique, énergie, Codac, corrections, non-régression)
```

Options communes : `--start AAAA-MM-JJ`, `--config autre.yaml`, `--etiquette nom` (nom des sorties de
`montecarlo` et `simuler`). Les données 2026 couvrent du 1er janvier au 2 novembre.

**Quota Open-Meteo** : 10 000 requêtes pondérées par jour. Le téléchargeur s'arrête de lui-même quand le quota
est atteint ; relancer la même commande le lendemain reprend là où il en était (les fichiers déjà en cache ne
sont jamais redemandés).

## Interface graphique

```bash
streamlit run app.py
```

| Onglet | Contenu |
|---|---|
| Configuration | date, largage, cercle d'arrivée, état de S1–S20, batterie, chauffage, nombre de runs. Enregistre une **copie** dans `configs/` ; l'original `config.yaml` n'est remplacé qu'après confirmation (sauvegarde `config.yaml.bak`). |
| Lancer | une mission, un Monte-Carlo ou le rapport complet, en arrière-plan : barre de progression, journal, bouton **Annuler** (arrête aussi les processus du pool). |
| Résultats | carte folium, courbes (énergie, vitesse, largeur de la boîte Codac), journal de bord ; figures du Monte-Carlo avec intervalles à 90 % ; tableau P1–P28 et valeur de chaque solution ; rapport. |
| Comparer | deux configurations (ou deux dates) côte à côte, mêmes graines : différence appariée de P(arrivée). |
| Mode histoire | l'équivalent de `python main.py histoire`, avec des boutons au lieu des questions du terminal. |
| Données | état du cache (Open-Meteo, années, couloir fin, GFW, côte, icebergs) et bouton de reprise du téléchargement. |

L'interface ne contient aucun calcul : elle appelle `main.py` (dans un sous-processus, pour ne pas bloquer la
page) et les fonctions de `sim/`. `main.py` fonctionne sans elle.

## Configuration

- [`config.yaml`](config.yaml) regroupe la mission (date, largage, cercle d'arrivée), la coque, l'énergie, la
  navigation, les pannes de capteurs et **l'état des solutions S1–S20** (`absente`, `partielle` ou `validee`).
  Chaque correction du modèle garde l'ancien comportement comme option (voir `HYPOTHESES.md`, H71–H78).
- [`risks.yaml`](risks.yaml) contient le registre P1–P28 : taux, modulateurs, effet des solutions, conséquences,
  cascades, priors de calibration.

## Icebergs (désactivé par défaut)

Les observations d'icebergs de 2026 ne sont pas en libre accès : le module reste désactivé
(`donnees.icebergs.active: false`) et aucune donnée n'est inventée (H08, H77).

**Obtenir les données.** International Ice Patrol Iceberg Sightings Database, distribuée par le NSIDC
(jeu G00807, https://nsidc.org/data/g00807). Le téléchargement demande un compte NASA **Earthdata** (gratuit,
https://urs.earthdata.nasa.gov). Les observations de la saison en cours sont publiées avec retard ; les bulletins
quotidiens de l'IIP (https://www.navcen.uscg.gov/international-ice-patrol-overview) peuvent servir à compléter.

**Format attendu de `data/icebergs.csv`** (UTF-8, séparateur virgule, une ligne d'en-tête, une observation par ligne) :

```csv
date,lat,lon,taille
2026-04-12,47.85,-48.20,M
2026-04-12T14:30:00Z,46.10,-47.55,GR
```

| Colonne | Contenu |
|---|---|
| `date` | date ou date-heure ISO 8601 de l'observation (UTC) |
| `lat` | latitude en degrés décimaux, nord positif |
| `lon` | longitude en degrés décimaux, est positif (donc négative dans l'Atlantique Ouest) |
| `taille` | facultatif : classe IIP `GR` growler, `BB` bergy bit, `S` small, `M` medium, `L` large, `VL` very large ; vide = `M` |

Puis `donnees.icebergs.active: true` dans `config.yaml`. Le rayon de recherche, la fenêtre de temps et les
issues d'un choc sont dans la même section (H77).

## Performances

Rapport complet (`--runs 500`, 14 processus sur 8 cœurs physiques) : 32 min au départ, 8,2 min maintenant,
**résultats identiques au bit près** (vérifié par `tests/test_non_regression.py`). Détail des gains dans le
rapport, section « Calcul ». Principes : profiler avec un échantillonneur (py-spy) plutôt qu'avec cProfile seul,
qui gonfle les petites fonctions et ne voit pas le temps passé dans Codac ; n'accepter que des optimisations
exactes (la trajectoire est chaotique : un écart d'un bit change l'issue de certaines missions) ; calculer une
seule fois les runs communs à plusieurs étapes du rapport.

## Organisation

```
app.py                  interface graphique (Streamlit)
sim/environment.py      données réelles : téléchargement, cache, années multiples, interpolation (t, lat, lon)
sim/boat.py             bilan de forces 2D (carène Testa, vagues, fardage, dérive)
sim/noyaux.py           noyau compilé (numba) de l'équilibre, identique au bit près à la version Python
sim/energy.py           solaire ERA5, batterie LiFePO4 thermique, chauffage, gestion S8 (prévision solaire)
sim/failures.py         aléas reproductibles (nombres aléatoires communs), pannes GPS et compas
sim/estimator_codac.py  localisation ensembliste garantie (CtcInverse), rejet des fix, marge de saut GPS
sim/arrondi.py          mode d'arrondi du processeur (vers le haut seulement pendant Codac)
sim/autopilot.py        guidage, crabe, modes dégradés, approche du cercle d'arrivée
sim/risks.py            registre P1–P28, chavirage par déferlement, priors, multiplicateurs, cascades
sim/icebergs.py         risque iceberg (si data/icebergs.csv est fourni)
sim/run.py              boucle de simulation
sim/montecarlo.py       Monte-Carlo parallèle (lot unique dédupliqué), contrefactuels, bootstrap hiérarchique
sim/effets.py           effet de chaque correction, activées une à une sur les mêmes graines
sim/annees.py           plusieurs années de météo : décomposition météo / modèle / hasard
sim/peche.py            captures : effet de la route
sim/analyse_energie.py  comparaison des politiques d'énergie S8
sim/taches.py           tâches en arrière-plan de l'interface (lancement, progression, annulation)
sim/story.py            récits « et si je ne le résous pas ? », mode histoire interactif
sim/profil.py           profilage
sim/report.py, carte.py, journal.py, rapport_mc.py, rapport_final.py, chauffage.py   sorties
```
