"""Comparaison des politiques d'énergie (S8) sur un ensemble de largages décalés.

Navigation parfaite et aucune panne : on isole l'effet de la politique. La trajectoire étant
chaotique (une fenêtre météo attrapée ou manquée), on compare des moyennes d'ensemble, pas un run.

    naive       S8 absente : moteur à la puissance de croisière jusqu'à la coupure du BMS
    regulation  S8 validée, ancienne loi (moyenne passée + cible de SOC)
    prevision   S8 validée, prévision solaire 24 h + veille de nuit [H74]
"""
from __future__ import annotations

import copy

import numpy as np

POLITIQUES = {
    "naive": {"S8": "absente"},
    "regulation": {"S8": "validee", "politique": "regulation"},
    "prevision": {"S8": "validee", "politique": "prevision", "prevision": "donnees"},
    "prevision_persistance": {"S8": "validee", "politique": "prevision", "prevision": "persistance"},
}


def config_politique(cfg, nom, start_iso):
    c = copy.deepcopy(cfg)
    p = POLITIQUES[nom]
    c["mission"]["start"] = start_iso
    c["solutions"]["S8"] = p["S8"]
    c["solutions"]["S6"] = "validee"
    for k in ("politique", "prevision"):
        if k in p:
            c["energie"]["validee"][k] = p[k]
    return c


def un_run(args):
    cfg, env, cote, jour_mesure = args
    from . import run as R
    r = R.Simulation(cfg, env, cote, dt=cfg["simulation"]["dt_montecarlo_s"],
                     modules=dict(estimateur=False, risques=False)).executer()
    tr = r.traj
    i = min(int(np.searchsorted(tr["t"], tr["t"][0] + jour_mesure * 86400.0)), len(tr["t"]) - 1)
    reste = 0.0 if (r.fin == "arrivee" and r.jours <= jour_mesure) else float(tr["dist_restante_nm"][i])
    return dict(arrivee=r.fin == "arrivee", jours=r.jours, reste_nm=reste, e_moteur=r.stats["e_moteur"],
                blackouts=r.stats["blackouts"])


def comparer(cfg, ctx, start_iso, politiques=None, n=12, pas_h=12.0, jour_mesure=30, max_days=150):
    """{politique: {arrivees, jour_median, reste_nm (moyenne à `jour_mesure`), ...}} sur n largages décalés."""
    from .run import iso, t_epoch
    t0 = t_epoch(start_iso)
    out = {}
    for nom in politiques or POLITIQUES:
        runs = []
        for k in range(n):
            c = config_politique(cfg, nom, iso(t0 + k * pas_h * 3600).replace(" ", "T") + ":00Z")
            c["mission"]["max_days"] = max_days
            runs.append(un_run((c, ctx.env, ctx.cote, jour_mesure)))
        out[nom] = dict(arrivees=sum(r["arrivee"] for r in runs), n=n,
                        jour_median=float(np.median([r["jours"] for r in runs])),
                        reste_nm=float(np.mean([r["reste_nm"] for r in runs])),
                        e_moteur_wh=float(np.mean([r["e_moteur"] for r in runs])),
                        blackouts=float(np.mean([r["blackouts"] for r in runs])), runs=runs)
    return out


def tableau(res: dict, jour_mesure=30) -> list[str]:
    L = [f"| Politique | Arrivées | Jour de fin (médiane) | Reste à parcourir au jour {jour_mesure} (nm, moyenne) | "
         "Énergie moteur (Wh) | Black-out par mission |", "|---|---|---|---|---|---|"]
    for nom, r in res.items():
        L.append(f"| {nom} | {r['arrivees']}/{r['n']} | {r['jour_median']:.0f} | {r['reste_nm']:.0f} | "
                 f"{r['e_moteur_wh']:.0f} | {r['blackouts']:.1f} |")
    return L
