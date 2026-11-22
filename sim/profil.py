"""Profilage (cProfile) d'une mission seule et d'un petit Monte-Carlo, dans un seul processus.

    python main.py profil            -> out/profil.txt (les fonctions les plus coûteuses)
"""
from __future__ import annotations

import cProfile
import copy
import io
import pstats
import time

from .config import OUT


def _tout_valide(cfg):
    c = copy.deepcopy(cfg)
    for s in c["solutions"]:
        c["solutions"][s] = "validee"
    return c


def profiler(cfg, chemin_env, n_mc=8, n_lignes=25, nom="profil") -> str:
    from . import montecarlo as MC
    from . import story
    ctx = story.Contexte(chemin_env)
    tv = _tout_valide(cfg)
    sorties = []

    def mesurer(titre, fn):
        pr = cProfile.Profile()
        t0 = time.perf_counter()
        pr.enable()
        fn()
        pr.disable()
        duree = time.perf_counter() - t0
        for tri in ("tottime", "cumulative"):
            buf = io.StringIO()
            pstats.Stats(pr, stream=buf).strip_dirs().sort_stats(tri).print_stats(n_lignes)
            lignes = buf.getvalue().splitlines()
            debut = next(i for i, x in enumerate(lignes) if "ncalls" in x)
            sorties.append(f"## {titre} — {duree:.2f} s (sous profileur) — tri : {tri}\n" + "\n".join(lignes[debut:]))

    mesurer("Mission seule (tout validé, pas de 30 min)", lambda: ctx.rejouer(tv, cfg["simulation"]["graine"], 0))
    plan = MC.plan(cfg, 25)[:n_mc]

    def petit_mc():
        for c in (cfg, tv):
            for k, g in plan:
                ctx.rejouer(c, g, k)

    mesurer(f"Petit Monte-Carlo ({n_mc} runs × 2 configurations, un processus)", petit_mc)
    # temps sans profileur (référence pour chiffrer les gains)
    t0 = time.perf_counter()
    petit_mc()
    sorties.insert(0, f"Petit Monte-Carlo sans profileur : {time.perf_counter() - t0:.2f} s "
                      f"({2 * n_mc} missions, grille {chemin_env})\n")
    OUT.mkdir(exist_ok=True)
    f = OUT / f"{nom}.txt"
    f.write_text("\n\n".join(sorties), encoding="utf-8")
    return str(f)
