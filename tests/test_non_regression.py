"""Non-régression : un petit Monte-Carlo doit redonner exactement la référence enregistrée.

Mêmes graines, mêmes jeux de paramètres, météo réelle en cache (grille à 2°, toujours disponible) :
la cause de fin et le jour de fin de chaque mission doivent être identiques. Trois configurations :
  - actuel       : le bateau d'aujourd'hui, modèle courant ;
  - tout_valide  : toutes les solutions validées, modèle courant ;
  - ancien       : tout validé avec l'ANCIEN modèle (corrections désactivées) : protège les options
                   « ancien comportement » et prouve que les optimisations ne changent pas les résultats.

Régénérer la référence après un changement VOLONTAIRE du modèle (à justifier dans HYPOTHESES.md) :
    python tests/test_non_regression.py --ecrire
"""
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from sim import boat as B  # noqa: E402
from sim import config as C  # noqa: E402
from sim.config import DATA  # noqa: E402

REFERENCE = pathlib.Path(__file__).with_name("reference_mc.json")
GRILLE = DATA / "grille_2deg.npz"
N_RUNS = 6


def _configs():
    from sim import effets
    cfg = C.charger()
    tout = copy.deepcopy(cfg)
    for s in tout["solutions"]:
        tout["solutions"][s] = "validee"
    return {"actuel": cfg, "tout_valide": tout, "ancien": effets.config_ancienne(tout)}


def calculer():
    from sim import montecarlo as MC
    from sim import story
    ctx = story.Contexte(GRILLE)
    out = {}
    for nom, cfg in _configs().items():
        out[nom] = []
        for k, g in MC.plan(cfg, 25)[:N_RUNS]:
            r = ctx.rejouer(cfg, g, k)
            out[nom].append({"jeu": k, "graine": g, "fin": r.fin, "jours": float(round(float(r.jours), 6)),
                             "cause": r.stats.get("cause_pid"), "problemes": sorted(r.occurrences)})
    return out


@pytest.mark.skipif(not GRILLE.exists() or not (DATA / "cote.wkb").exists() or not (DATA / "gfw.npz").exists(),
                    reason="cache de données absent (python main.py donnees)")
def test_petit_monte_carlo_identique_a_la_reference():
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    obtenu = calculer()
    for nom in ref:
        for a, b in zip(ref[nom], obtenu[nom]):
            assert a == b, f"{nom}, graine {a['graine']} : attendu {a}, obtenu {b}"
    # taux d'arrivée : identique (tolérance du cahier des charges : 0,5 point)
    for nom in ref:
        p_ref = sum(r["fin"] == "arrivee" for r in ref[nom]) / len(ref[nom])
        p_obt = sum(r["fin"] == "arrivee" for r in obtenu[nom]) / len(obtenu[nom])
        assert abs(p_ref - p_obt) <= 0.005


def test_equilibre_optimise_identique_a_la_version_de_reference():
    """La bissection optimisée (sans appels de méthode) donne exactement les mêmes vitesses que la
    version d'origine, sur un balayage de puissances, vents, vagues et encrassements."""
    co = B.Coque.depuis_config(C.charger())
    n = 0
    for p in (0.0, 0.4, 3.0, 21.0, 40.0, 60.0):
        for fx in (-60.0, -8.0, -0.3, 0.0, 0.7, 15.0):
            for rv in (0.0, 2.5, 30.0):
                for encr in (0.0, 0.3):
                    assert B._resoudre_axe(co, p, fx, rv, encr) == B._resoudre_axe_reference(co, p, fx, rv, encr)
                    n += 1
    assert n == 216


_DONNEES = pytest.mark.skipif(not GRILLE.exists() or not (DATA / "cote.wkb").exists() or not (DATA / "gfw.npz").exists(),
                              reason="cache de données absent (python main.py donnees)")


@_DONNEES
def test_lot_unique_identique_aux_appels_separes():
    """MC.lancer_lot (un seul pool, tâches dédupliquées et réordonnées) == MC.lancer appelé étape par étape."""
    from sim import montecarlo as MC
    cfg = C.charger()
    autre = copy.deepcopy(cfg)
    autre["solutions"]["S19"] = "validee"
    etapes = {"a": ({"actuel": cfg}, 25), "b": ({"reference": copy.deepcopy(cfg), "S19": autre}, 25)}
    lot = MC.lancer_lot(etapes, GRILLE, processus=4, journal=lambda *_: None)
    for nom, (configs, n) in etapes.items():
        separe = MC.lancer(configs, n, GRILLE, processus=4, journal=lambda *_: None)
        assert lot[nom] == separe, nom


@_DONNEES
def test_trajectoire_allegee_meme_resume():
    """En Monte-Carlo on n'enregistre que les séries utiles au résumé : le résumé doit être identique."""
    from dataclasses import asdict

    from sim import montecarlo as MC
    from sim import run as R
    MC._init_worker(str(GRILLE))
    cfg = _configs()["tout_valide"]
    for k, g in MC.plan(cfg, 25)[:2]:
        res = []
        for champs in (None, MC.CHAMPS_RESUME):
            sim = R.Simulation(cfg, MC._G["env"], MC._G["cote"], graine=g, jeu=MC._jeu(cfg, k), densites=MC._G["dens"],
                               registre_yaml=MC._G["reg"], dt=cfg["simulation"]["dt_montecarlo_s"], champs_traj=champs)
            res.append(asdict(MC._resumer("x", sim.executer(), k, g)))
        assert res[0] == res[1]


def test_noyau_numba_identique_au_python():
    """Le noyau compilé (numba) de l'équilibre donne les mêmes bits que la version Python."""
    import random
    co_a, co_b = B.Coque.depuis_config(C.charger()), B.Coque.depuis_config(C.charger())
    rnd = random.Random(7)
    for _ in range(5000):
        args = (rnd.choice([0.0, rnd.uniform(0, 70)]), rnd.uniform(-7, 7), rnd.gauss(0, 10), rnd.gauss(0, 10),
                rnd.gauss(0, .5), rnd.gauss(0, .5), abs(rnd.gauss(2.5, 2)), rnd.gauss(0, 1), rnd.gauss(0, 1),
                rnd.choice([0.0, rnd.uniform(0, .5)]), 0.72)
        assert B.equilibre(co_a, *args) == B._equilibre_py(co_b, *args)


def test_bootstrap_compile_identique_a_numpy():
    """Le bootstrap compilé (numba) donne exactement les mêmes intervalles que la boucle numpy."""
    import random

    from sim import montecarlo as MC
    from sim import noyaux
    if not noyaux.NUMBA:
        pytest.skip("numba absent")
    rnd = random.Random(3)
    for taille_jeu in (1, 3, 8, 20):
        runs = [{"jeu": j, "v": rnd.random() * rnd.choice([1.0, 1e-3, 120.0])} for j in range(25)
                for _ in range(taille_jeu)]
        a = MC.bootstrap(runs, lambda r: r["v"])
        noyaux.NUMBA = False
        try:
            b = MC.bootstrap(runs, lambda r: r["v"])
        finally:
            noyaux.NUMBA = True
        assert a == b


def test_codac_ne_laisse_pas_l_arrondi_vers_le_haut():
    """[H78] `import codac` met le processeur en arrondi vers le haut ; le simulateur doit revenir au plus
    proche après chaque calcul Codac, sinon un run ne donne pas les mêmes bits selon ce qui a tourné avant."""
    from sim import arrondi as AR
    from sim.estimator_codac import EstimateurCodac
    if AR.mode_actuel() is None:
        pytest.skip("mode d'arrondi non lisible sur cette plateforme")
    cfg = C.charger()
    e = EstimateurCodac(cfg, 47.0, -48.0, 0.0)
    e.predire(0.0, 1800.0, 0.8, 90.0)
    e.largeur_m(), e.centre_local()
    assert AR.mode_actuel() == AR.PROCHE
    x = [0.1 * i for i in range(1, 50)]
    assert sum(x) == 122.50000000000001        # valeur au plus proche (vers le haut : 122.50000000000003)


if __name__ == "__main__":
    if "--ecrire" in sys.argv:
        REFERENCE.write_text(json.dumps(calculer(), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Référence écrite : {REFERENCE}")
    else:
        print(__doc__)
