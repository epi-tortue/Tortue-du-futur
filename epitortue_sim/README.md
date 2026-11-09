# Simulateur de mission Epi'Tortue

*« Si on avait lancé le bateau le 1er janvier 2026, que lui serait-il probablement arrivé ? »*

Le simulateur rejoue la **météo, les vagues, les courants et la pêche réels de 2026**, y plonge un modèle du
bateau (coque finale [Testa](https://github.com/epi-tortue/Testa), énergie solaire, batterie, autopilote, estimateur
**Codac**) avec les **28 problèmes P1–P28** de la [doc](https://epi-tortue.github.io/docs/), puis produit une
histoire (journal de bord, carte) et une statistique d'issues (Monte-Carlo). C'est un scénario plausible, **pas
une prédiction** : toutes les hypothèses chiffrées sont dans [HYPOTHESES.md](HYPOTHESES.md).

## Installation

```bash
pip install numpy scipy pandas matplotlib pyyaml requests shapely pvlib folium codac gfw-api-python-client pytest
```

Le jeton Global Fishing Watch se met dans `secrets.yaml` (`gfw_api_access_token: "..."`) ou dans la variable
d'environnement `GFW_API_ACCESS_TOKEN`. Ce fichier est ignoré par git.

## Utilisation

```bash
python main.py donnees                 # télécharge et met en cache (reprenable ; ensuite hors-ligne)
python main.py donnees --fine          # + couloir à 1° (plusieurs jours de quota Open-Meteo)
python main.py controle                # figure de contrôle : vent, vagues, courants, pêche au 01/01/2026
python main.py --start 2026-01-01 --runs 500     # rapport complet -> out/rapport_20260101.md
python main.py histoire --start 2026-01-01       # mode histoire interactif
python main.py simuler --graine 7                # une mission : carte HTML, courbes, journal de bord
python main.py chauffage                         # chauffer la batterie : coût et gain
python main.py montecarlo --runs 500             # issues seules
python main.py calibration                       # contrôle : tout « partiel » ≈ historique Microtransat
python -m pytest                                 # tests (énergie, physique, garantie Codac, contrefactuels)
```

Pour essayer une autre date, il suffit de passer `--start AAAA-MM-JJ`. Les données couvrent du 1er janvier au
2 novembre 2026.

## Configuration

- [`config.yaml`](config.yaml) regroupe la mission (date, largage, cercle d'arrivée), la coque, l'énergie, la
  navigation, les pannes de capteurs et **l'état des solutions S1–S20** (`absente`, `partielle` ou `validee`).
  Vous y cochez ce qui est réellement fait.
- [`risks.yaml`](risks.yaml) contient le registre P1–P28 : taux, modulateurs, effet des solutions, conséquences,
  cascades, priors de calibration.

## Organisation

```
sim/environment.py      données réelles : téléchargement, cache, interpolation (t, lat, lon)
sim/boat.py             bilan de forces 2D (carène Testa, vagues, fardage, dérive)
sim/energy.py           solaire ERA5, batterie LiFePO4 thermique, chauffage, gestion S8
sim/failures.py         aléas reproductibles (nombres aléatoires communs), pannes GPS et compas
sim/estimator_codac.py  localisation ensembliste garantie (CtcInverse), rejet des fix, biais compas
sim/autopilot.py        guidage, crabe, modes dégradés
sim/risks.py            registre P1–P28, priors, multiplicateurs, cascades
sim/run.py              boucle de simulation
sim/montecarlo.py       Monte-Carlo parallèle, contrefactuels, bootstrap hiérarchique
sim/story.py            récits « et si je ne le résous pas ? », mode histoire interactif
sim/report.py, carte.py, journal.py, rapport_mc.py, rapport_final.py, chauffage.py   sorties
```
