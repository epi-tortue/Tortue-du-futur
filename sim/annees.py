"""Plusieurs années de météo : même date de départ rejouée chaque année [H76].

Question : dans l'intervalle à 90 % de P(arrivée), quelle part vient de la météo de l'année (que personne
ne connaît à l'avance) et quelle part vient du modèle (taux de pannes incertains, 25 jeux de paramètres) ?

Plan : pour chaque année de `donnees.annees`, mêmes jeux de paramètres, mêmes graines (nombres aléatoires
communs), départ le même jour du calendrier. Toutes les années sont simulées sur la grille à 2° : c'est
la seule téléchargée pour les années passées, et comparer 2026 à 1° avec 2024 à 2° mélangerait deux effets.

Décomposition de la variance de l'indicateur « arrivée » Y (loi de la variance totale, ANOVA à deux
facteurs croisés année × jeu, sans interaction séparable avec 8 runs par case) :
  - météo       : variance entre années des taux d'arrivée par année, corrigée du bruit d'échantillonnage ;
  - modèle      : variance entre jeux de paramètres des taux par jeu (toutes années confondues), corrigée ;
  - hasard      : le reste (pannes et rencontres tirées au sort, à paramètres et météo fixés).
On publie les écarts-types en points de probabilité : ils se comparent directement aux intervalles.

    python main.py annees [--runs N]      -> out/annees_<date>.md et .json
"""
from __future__ import annotations

import copy
import json

import numpy as np

from . import environment as E
from . import montecarlo as MC
from . import rapport_mc as RM
from .config import DATA, OUT


def _tout(cfg, etat="validee"):
    c = copy.deepcopy(cfg)
    for s in c["solutions"]:
        c["solutions"][s] = etat
    return c


def _date_annee(iso_: str, annee: int) -> str:
    return f"{annee}{iso_[4:]}"


def grille_annee(cfg, annee: int):
    """Grille principale (2°) d'une année ; None si elle n'est pas en cache."""
    f = DATA / E.nom_grille(cfg["donnees"]["grille"], annee, cfg)
    return f if f.exists() else None


def composantes(runs_par_annee: dict, f=lambda r: r["fin"] == "arrivee") -> dict:
    """Écarts-types (en probabilité) dus à la météo, au modèle et au hasard. runs_par_annee : {année: [runs]}."""
    ys = {a: np.array([float(f(r)) for r in runs]) for a, runs in runs_par_annee.items()}
    tout = np.concatenate(list(ys.values()))
    var_tot = float(np.var(tout))
    p_annee = {a: float(v.mean()) for a, v in ys.items()}
    n_annee = np.mean([len(v) for v in ys.values()])
    # par jeu, toutes années confondues
    par_jeu = {}
    for a, runs in runs_par_annee.items():
        for r in runs:
            par_jeu.setdefault(r["jeu"], []).append(float(f(r)))
    m_jeu = np.array([np.mean(v) for v in par_jeu.values()])
    n_jeu = np.mean([len(v) for v in par_jeu.values()])
    p = float(tout.mean())
    bruit = p * (1 - p)                                   # variance d'un run (Bernoulli)
    var_meteo = max(0.0, float(np.var(list(p_annee.values()), ddof=1)) - bruit / n_annee) if len(ys) > 1 else 0.0
    var_modele = max(0.0, float(np.var(m_jeu, ddof=1)) - bruit / n_jeu) if len(m_jeu) > 1 else 0.0
    var_hasard = max(0.0, var_tot - var_meteo - var_modele)
    return dict(p=p, p_annee=p_annee, sd_meteo=var_meteo ** 0.5, sd_modele=var_modele ** 0.5,
                sd_hasard=var_hasard ** 0.5, var_totale=var_tot, n=len(tout))


def etudier(cfg, n_runs=200, journal=print) -> str:
    annees = sorted({int(a) for a in cfg["donnees"].get("annees", [])} | {E.annee_de_base(cfg)})
    dispo = {a: grille_annee(cfg, a) for a in annees}
    manque = [a for a, g in dispo.items() if g is None]
    annees = [a for a in annees if dispo[a] is not None]
    if len(annees) < 2:
        raise SystemExit(f"Moins de deux années en cache (manquent : {manque}) : python main.py donnees --annees")
    departs = {"hiver": cfg["mission"]["start"], "ete": cfg["mission"]["comparaison_ete"]}
    res = {}                                               # res[depart][config][annee] = runs
    for a in annees:
        etapes = {}
        for nd, d in departs.items():
            c = copy.deepcopy(cfg)
            c["mission"]["start"] = _date_annee(d, a)
            etapes[nd] = ({"actuel": c, "tout_valide": _tout(c)}, n_runs)
        journal(f"[{a}] grille {dispo[a].name}")
        lot = MC.lancer_lot(etapes, dispo[a], journal=journal)
        for nd in departs:
            for etq, runs in lot[nd].items():
                res.setdefault(nd, {}).setdefault(etq, {})[a] = runs
    succes = lambda r: r["fin"] == "arrivee"  # noqa: E731
    et = cfg["mission"]["start"][:10].replace("-", "")
    L = [f"# Plusieurs années de météo — départ le {cfg['mission']['start'][5:10]} "
         f"({', '.join(map(str, annees))})", "",
         f"Même jour de départ, mêmes jeux de paramètres et mêmes graines chaque année ({n_runs} runs par année et "
         "par configuration), grille météo à 2° pour toutes les années. Intervalles à 90 % (bootstrap sur les jeux "
         "de paramètres puis sur les runs)." + (f" Années absentes du cache : {manque}." if manque else ""), "",
         "| Départ | Configuration | " + " | ".join(str(a) for a in annees) + " |",
         "|---|---|" + "---|" * len(annees)]
    synth = {}
    for nd in departs:
        for etq in ("actuel", "tout_valide"):
            cells = [RM.ic(MC.bootstrap(res[nd][etq][a], succes)) for a in annees]
            L.append(f"| {nd} | {etq.replace('_', ' ')} | " + " | ".join(cells) + " |")
            synth[f"{nd}_{etq}"] = composantes(res[nd][etq])
    L += ["", "## D'où vient l'incertitude ?", "",
          "Écarts-types de P(arrivée), en points de pourcentage. **Météo** : différence d'une année à l'autre ; "
          "**modèle** : différence d'un jeu de paramètres à l'autre (taux de pannes et de rencontres incertains) ; "
          "**hasard** : tirage des pannes à météo et paramètres fixés (il se moyenne sur les runs et ne pèse pas "
          "sur l'estimation). Les deux premiers sont corrigés du bruit d'échantillonnage.", "",
          "| Départ, configuration | P(arrivée), toutes années | Météo | Modèle | Rapport météo / modèle |",
          "|---|---|---|---|---|"]
    for k, c in synth.items():
        ratio = c["sd_meteo"] / c["sd_modele"] if c["sd_modele"] > 0 else float("inf")
        L.append(f"| {k.replace('_', ' ')} | {RM.pct(c['p'])} | ± {100 * c['sd_meteo']:.1f} | "
                 f"± {100 * c['sd_modele']:.1f} | {ratio:.2f} |")
    L += ["", "Lecture : si la colonne « météo » domine, une seule année de données ne suffit pas à conclure, "
          "même avec un modèle parfait ; si c'est le « modèle », il faut mieux connaître les taux de pannes "
          "(essais, retours d'expérience) avant de gagner en précision. Trois années ne donnent qu'une estimation "
          "grossière de la variabilité météo : à lire comme un ordre de grandeur."]
    OUT.mkdir(exist_ok=True)
    f = OUT / f"annees_{et}.md"
    f.write_text("\n".join(L), encoding="utf-8")
    (OUT / f"annees_{et}.json").write_text(json.dumps(
        {"annees": annees, "n_runs": n_runs, "synthese": synth,
         "taux": {nd: {etq: {str(a): MC.bootstrap(v, succes) for a, v in d.items()} for etq, d in res[nd].items()}
                  for nd in res}}, ensure_ascii=False), encoding="utf-8")
    journal(f"Années multiples : {f}")
    return str(f)
