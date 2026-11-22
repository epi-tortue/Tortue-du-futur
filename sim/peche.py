"""Captures par les pêcheurs : l'écart avec l'historique vient-il de la route ? [H73]

Le contrôle de calibration (toutes solutions « partielles », départ d'été) donne moins de fins par capture
que l'historique Microtransat (9–10 sur ≈ 30 tentatives, ≈ 32 %). Hypothèse : la mission part au large
(47°N 48°W), alors que les tentatives historiques partaient près des côtes de Terre-Neuve et traversaient
les Grands Bancs, l'une des zones les plus pêchées de l'Atlantique Nord.

Expérience : même scénario, deux routes, MÊME calage du taux de rencontre (la densité de référence H45 reste
celle de la route de la mission, via `calibration.route_reference`). Sans cette précaution, le calage
suivrait la route et compenserait l'effet qu'on veut mesurer.

    python main.py peche [--runs N]       -> out/peche_<date>.md et .json
"""
from __future__ import annotations

import copy
import json

from . import montecarlo as MC
from . import rapport_mc as RM
from .config import OUT

CAPTURE = ("capture", "perdu_filet")


def _scenario_historique(cfg):
    c = copy.deepcopy(cfg)
    for s in c["solutions"]:
        c["solutions"][s] = "partielle"
    c["mission"]["start"] = cfg["mission"]["comparaison_ete"]
    return c


def configs(cfg) -> dict:
    """{nom: cfg} : route de la mission et route côtière, densité de référence commune."""
    hist = _scenario_historique(cfg)
    ref_route = {"depart": dict(cfg["mission"]["depart"]), "arrivee": dict(cfg["mission"]["arrivee"])}
    base = copy.deepcopy(hist)
    base.setdefault("registre_surcharges", {}).setdefault("calibration", {})["route_reference"] = ref_route
    cot = copy.deepcopy(base)
    rc = cfg["analyses"].get("route_cotiere") or {"depart": {"lat": 47.6, "lon": -52.4}}
    cot["mission"]["depart"].update({"lat": rc["depart"]["lat"], "lon": rc["depart"]["lon"]})
    return {"route_mission": base, "route_cotiere": cot}


def etudier(cfg, chemin_env, n_runs=200, journal=print) -> str:
    cs = configs(cfg)
    res = MC.lancer_lot({"peche": (cs, n_runs)}, chemin_env, journal=journal)["peche"]
    capt = lambda r: r["fin"] in CAPTURE  # noqa: E731
    rencontre = lambda r: r["occurrences"].get("P24", 0) > 0  # noqa: E731
    out = {}
    for nom, runs in res.items():
        out[nom] = {"captures": MC.bootstrap(runs, capt), "au_moins_une_rencontre": MC.bootstrap(runs, rencontre),
                    "jours_median": float(sorted(r["jours_fin"] for r in runs)[len(runs) // 2])}
    out["ecart_route"] = MC.bootstrap_diff(res["route_mission"], res["route_cotiere"], capt)
    d = cs["route_cotiere"]["mission"]["depart"]
    et = cfg["mission"]["start"][:10].replace("-", "")
    L = ["# Captures par les pêcheurs : effet de la route", "",
         f"Scénario « historique » (toutes solutions partielles, départ le {cfg['mission']['comparaison_ete'][:10]}), "
         f"{n_runs} runs par route, mêmes graines. Route côtière : départ {d['lat']}°N {abs(d['lon'])}°W (large de "
         "St John's, Terre-Neuve), à travers les Grands Bancs. Le taux de rencontre reste calé sur la densité de "
         "pêche de la route de la mission (H45, H73). Intervalles à 90 %.", "",
         "| Route | Fin par capture (P23/P24) | Au moins une rencontre de pêche | Jour de fin médian |",
         "|---|---|---|---|"]
    for nom in ("route_mission", "route_cotiere"):
        o = out[nom]
        L.append(f"| {nom.replace('_', ' ')} | {RM.ic(o['captures'])} | {RM.ic(o['au_moins_une_rencontre'])} | "
                 f"{o['jours_median']:.0f} |")
    e = out["ecart_route"]
    L += ["", f"Écart dû à la route (côtière − mission, runs appariés) : {RM.ic(e)}.", "",
          "Historique cité : 9–10 captures sur ≈ 30 tentatives (≈ 32 %). Si la route côtière s'en approche, "
          "l'écart venait de la route ; l'écart restant est porté par `rencontres.facteur_rencontre` "
          "(risks.yaml, défaut 1, H73). Ne le recaler que si un écart reste inexpliqué par une donnée."]
    OUT.mkdir(exist_ok=True)
    f = OUT / f"peche_{et}.md"
    f.write_text("\n".join(L), encoding="utf-8")
    (OUT / f"peche_{et}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    journal(f"Étude pêche : {f}")
    return str(f)
