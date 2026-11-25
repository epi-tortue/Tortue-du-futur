"""Monte-Carlo : météo réelle identique, pannes / rencontres / paramètres tirés.

Plan d'expérience
-----------------
- `jeux_parametres` jeux de paramètres (incertitude épistémique) × runs par jeu (aléa).
- La graine d'un run est déterminée par (jeu, k) : deux configurations comparées
  (avec / sans une solution) voient exactement les mêmes tirages (nombres aléatoires communs).
- Intervalles à 90 % : bootstrap hiérarchique (on rééchantillonne les jeux, puis les runs).
"""
from __future__ import annotations

import copy
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass

import numpy as np

from .config import OUT

_G = {}


def _init_worker(chemin_env):
    import warnings
    warnings.filterwarnings("ignore")
    from . import environment as E
    from . import risks as RK
    _G["env"] = E.Environnement(chemin_env)
    _G["cote"] = E.charger_cote()
    _G["reg"] = RK.charger_registre()
    _G["dens"] = RK.Densites()
    _G["jeux"] = {}


def _jeu(cfg, k):
    from . import risks as RK
    cle = (k, cfg["mission"]["depart"]["lat"], cfg["mission"]["depart"]["lon"],
           cfg["mission"]["arrivee"]["lat"], cfg["mission"]["arrivee"]["lon"], RK.signature_registre(cfg))
    if cle not in _G["jeux"]:
        _G["jeux"][cle] = RK.tirer_parametres(RK.registre_pour(cfg, _G["reg"]), cfg, k, _G["dens"])
    return _G["jeux"][cle]


@dataclass
class Resume:
    etiquette: str
    jeu: int
    graine: int
    fin: str
    cause_pid: str | None
    jours_fin: float
    issue_physique: str
    retrouve: bool
    lat_fin: float
    lon_fin: float
    lat_fin_mission: float
    lon_fin_mission: float
    dist_restante_nm: float
    occurrences: dict
    premiere_j: dict
    premier_probleme: str | None
    e_solaire: float
    e_moteur: float
    e_chauffage: float
    blackouts: int
    hors_boite: int
    trace: list


def _resumer(etq, r, jeu, graine) -> Resume:
    tr = r.traj
    t0 = tr["t"][0]
    i_fin = int(np.searchsorted(tr["t"], r.t_fin)) if len(tr["t"]) else 0
    i_fin = min(i_fin, len(tr["t"]) - 1)
    prem = {k: (v - t0) / 86400.0 for k, v in r.premiere.items()}
    graves = [e for e in r.evenements if e.probleme and e.gravite >= 2 and e.probleme in r.premiere]
    pp = graves[0].probleme if graves else (min(prem, key=prem.get) if prem else None)
    pas = max(1, len(tr["t"]) // 400)
    trace = [(round(float(a), 3), round(float(b), 3)) for a, b in zip(tr["lat"][::pas], tr["lon"][::pas])]
    return Resume(etq, jeu, graine, r.fin, r.stats.get("cause_pid"), r.jours, r.issue_physique, r.retrouve,
                  float(tr["lat"][-1]), float(tr["lon"][-1]), float(tr["lat"][i_fin]), float(tr["lon"][i_fin]),
                  float(tr["dist_restante_nm"][i_fin]), dict(r.occurrences), prem, pp,
                  r.stats["e_solaire"], r.stats["e_moteur"], r.stats["e_chauffage"], r.stats["blackouts"],
                  r.stats.get("hors_boite", 0), trace)


# séries de la trajectoire lues par _resumer (les autres ne servent qu'aux runs détaillés)
CHAMPS_RESUME = ("t", "lat", "lon", "dist_restante_nm")


def _executer_un(args):
    etq, cfg, jeu_k, graine = args
    from . import run as R
    sim = R.Simulation(cfg, _G["env"], _G["cote"], graine=graine, jeu=_jeu(cfg, jeu_k), densites=_G["dens"],
                       registre_yaml=_G["reg"], dt=cfg["simulation"]["dt_montecarlo_s"], enregistrer_tout=True,
                       champs_traj=CHAMPS_RESUME)
    r = sim.executer()
    return asdict(_resumer(etq, r, jeu_k, graine))


def plan(cfg, n_runs, n_jeux=None):
    from . import risks as RK
    n_jeux = n_jeux or RK.charger_registre()["calibration"]["jeux_parametres"]
    par_jeu = max(1, int(math.ceil(n_runs / n_jeux)))
    base = int(cfg["simulation"]["graine"])
    return [(k, base * 100_000 + k * 1000 + j) for k in range(n_jeux) for j in range(par_jeu)][:max(n_runs, n_jeux)]


def lancer(configs: dict, n_runs: int, chemin_env, processus=None, journal=print) -> dict:
    """configs : {étiquette: cfg}. Retourne {étiquette: [Resume dict]}. Mêmes (jeu, graine) pour toutes."""
    any_cfg = next(iter(configs.values()))
    from .environment import Environnement
    Environnement(chemin_env)            # prépare le cache empilé AVANT de lancer les processus
    pl = plan(any_cfg, n_runs)
    taches = [(etq, cfg, k, g) for etq, cfg in configs.items() for (k, g) in pl]
    processus = processus or any_cfg["simulation"].get("processus") or max(1, (os.cpu_count() or 2) - 2)
    res = {etq: [] for etq in configs}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=processus, initializer=_init_worker, initargs=(str(chemin_env),)) as ex:
        for i, out in enumerate(ex.map(_executer_un, taches, chunksize=4)):
            res[out["etiquette"]].append(out)
            if (i + 1) % max(1, len(taches) // 10) == 0:
                journal(f"  {i + 1}/{len(taches)} runs ({time.time() - t0:.0f} s)")
    return res


def _executer_physique(args):
    cfg, modules = args
    from . import run as R
    r = R.Simulation(cfg, _G["env"], _G["cote"], dt=cfg["simulation"]["dt_montecarlo_s"], modules=modules).executer()
    return {"fin": r.fin, "jours": r.jours, "reste_nm": float(r.traj["dist_restante_nm"][-1]),
            "stats": {k: v for k, v in r.stats.items() if isinstance(v, (int, float, bool))}}


def lancer_physique(cfgs: list, chemin_env, modules=None, processus=None, on_result=None) -> list[dict]:
    """Missions sans tirage de pannes (analyses physiques : chauffage, cercle d'arrivée), en parallèle.

    Même résultat que de les enchaîner dans le processus principal (aucun aléa partagé entre missions) ;
    retourne, dans l'ordre de `cfgs`, {fin, jours, reste_nm, stats}. `on_result(index, resultat)` est
    appelé après chaque mission terminée."""
    modules = modules or dict(estimateur=False, risques=False)
    processus = processus or cfgs[0]["simulation"].get("processus") or max(1, (os.cpu_count() or 2) - 2)
    with ProcessPoolExecutor(max_workers=min(processus, len(cfgs)), initializer=_init_worker,
                             initargs=(str(chemin_env),)) as ex:
        res = []
        for i, out in enumerate(ex.map(_executer_physique, [(c, modules) for c in cfgs])):
            res.append(out)
            if on_result is not None:
                on_result(i, out)
        return res


def _cout_estime(cfg) -> float:
    """Ordre de grandeur de la durée d'un run : plus il y a de solutions validées, plus la mission dure
    (elle va jusqu'à l'arrivée au lieu de s'arrêter au bout de quelques jours). Sert seulement à lancer
    les tâches longues en premier pour que les processus finissent ensemble."""
    return sum(v == "validee" for v in cfg["solutions"].values()) + 0.5 * sum(
        v == "partielle" for v in cfg["solutions"].values())


def lancer_lot(etapes: dict, chemin_env, processus=None, journal=print, on_result=None, plans=None) -> dict:
    """Plusieurs Monte-Carlo dans UN seul pool de processus.

    etapes : {nom: (configs, n_runs)} avec configs = {étiquette: cfg}. Retourne {nom: {étiquette: [Resume]}},
    exactement ce que renverraient des appels séparés à `lancer` (mêmes graines, mêmes résultats). Gains :
      - un seul démarrage de processus (import, chargement de la météo) au lieu d'un par étape ;
      - tâches identiques (même configuration, même jeu, même graine) calculées une seule fois : la
        « référence » des contrefactuels est un sous-ensemble du Monte-Carlo principal ;
      - tâches longues en premier : pas de processus qui travaille seul à la fin d'une étape.

    `on_result(cle, resultat)` est appelé après chaque run terminé. `plans`, s'il est fourni, permet de
    préciser les couples (jeu, graine) à lancer pour chaque (étape, configuration).
    """
    any_cfg = next(iter(next(iter(etapes.values()))[0].values()))
    from .environment import Environnement
    Environnement(chemin_env)
    uniques = {}                     # clé -> (cfg, k, g)
    demandes = []                    # (nom, étiquette, clé)
    plans = plans or {}
    for nom, (configs, n_runs) in etapes.items():
        for etq, cfg in configs.items():
            sig = json.dumps(cfg, sort_keys=True, default=str)
            plan_config = plans[(nom, etq)] if (nom, etq) in plans else plan(cfg, n_runs)
            for (k, g) in plan_config:
                cle = (sig, k, g)
                uniques.setdefault(cle, (cfg, k, g))
                demandes.append((nom, etq, cle))
    cles = sorted(uniques, key=lambda c: -_cout_estime(uniques[c][0]))      # tri stable : ordre du plan conservé
    taches = [("_", uniques[c][0], uniques[c][1], uniques[c][2]) for c in cles]
    processus = processus or any_cfg["simulation"].get("processus") or max(1, (os.cpu_count() or 2) - 2)
    journal(f"  {len(demandes)} runs demandés, {len(taches)} à calculer ({len(demandes) - len(taches)} réutilisés), "
            f"{processus} processus")
    calcules = {}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=processus, initializer=_init_worker, initargs=(str(chemin_env),)) as ex:
        for i, (cle, out) in enumerate(zip(cles, ex.map(_executer_un, taches, chunksize=2))):
            calcules[cle] = out
            if on_result is not None:
                on_result(cle, out)
            if (i + 1) % max(1, len(taches) // 20) == 0:
                journal(f"  {i + 1}/{len(taches)} runs ({time.time() - t0:.0f} s)")
    res = {nom: {etq: [] for etq in configs} for nom, (configs, _) in etapes.items()}
    for nom, etq, cle in demandes:
        r = dict(calcules[cle])
        r["etiquette"] = etq
        res[nom][etq].append(r)
    return res


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------
def bootstrap(runs, f, n=2000, graine=0):
    """Intervalle à 90 % de mean(f(run)) par bootstrap hiérarchique (jeux puis runs)."""
    if not runs:
        return (float("nan"),) * 3
    par_jeu = {}
    for r in runs:
        par_jeu.setdefault(r["jeu"], []).append(float(f(r)))
    groupes = [np.array(v) for v in par_jeu.values()]
    rng = np.random.default_rng(graine)
    est = float(np.mean(np.concatenate(groupes)))
    from . import noyaux
    if noyaux.NUMBA:
        # même algorithme compilé : mêmes tirages, mêmes sommes, mêmes intervalles (test de non-régression)
        tailles = np.array([len(x) for x in groupes], dtype=np.int64)
        debuts = np.concatenate([[0], np.cumsum(tailles)[:-1]]).astype(np.int64)
        vals = noyaux.bootstrap_valeurs(rng, np.concatenate(groupes).astype(np.float64), debuts, tailles, n)
        return est, float(np.percentile(vals, 5)), float(np.percentile(vals, 95))
    vals = np.empty(n)
    for b in range(n):
        gs = rng.integers(0, len(groupes), len(groupes))
        tot = cnt = 0.0
        for g in gs:
            x = groupes[g]
            ech = x[rng.integers(0, len(x), len(x))]
            tot += ech.sum()
            cnt += len(ech)
        vals[b] = tot / cnt
    return est, float(np.percentile(vals, 5)), float(np.percentile(vals, 95))


def bootstrap_diff(runs_a, runs_b, f, n=2000, graine=0):
    """Intervalle de E[f(b)] − E[f(a)] sur des runs appariés (même jeu, même graine)."""
    da = {(r["jeu"], r["graine"]): float(f(r)) for r in runs_a}
    db = {(r["jeu"], r["graine"]): float(f(r)) for r in runs_b}
    paires = {}
    for k in da.keys() & db.keys():
        paires.setdefault(k[0], []).append(db[k] - da[k])
    if not paires:
        return (float("nan"),) * 3
    return bootstrap([{"jeu": j, "v": v} for j, vs in paires.items() for v in vs], lambda r: r["v"], n, graine)


def issues(runs):
    out = {}
    for c in sorted({r["fin"] for r in runs}):
        out[c] = bootstrap(runs, lambda r, c=c: r["fin"] == c)
    return out


def sauver(res: dict, nom: str):
    OUT.mkdir(exist_ok=True)
    f = OUT / f"mc_{nom}.json"
    f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return f


def charger(nom: str):
    return json.loads((OUT / f"mc_{nom}.json").read_text(encoding="utf-8"))


def configs_contrefactuelles(cfg, mode="ajout"):
    """ajout : config actuelle + Sx validée ; retrait : tout validé sauf Sx (à l'état de la config)."""
    out = {"reference": copy.deepcopy(cfg)}
    tout = copy.deepcopy(cfg)
    for s in tout["solutions"]:
        tout["solutions"][s] = "validee"
    if mode == "retrait":
        out = {"reference": tout}
    for s in cfg["solutions"]:
        if mode == "ajout":
            if cfg["solutions"][s] == "validee":
                continue
            c = copy.deepcopy(cfg)
            c["solutions"][s] = "validee"
        else:
            c = copy.deepcopy(tout)
            c["solutions"][s] = cfg["solutions"][s] if cfg["solutions"][s] != "validee" else "absente"
        out[s] = c
    return out
