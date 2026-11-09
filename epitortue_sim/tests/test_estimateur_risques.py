"""Tests d'intégration : estimateur Codac (garantie) et registre des risques (contrefactuels).

Ils utilisent les données réelles en cache (grille assemblée) ; ignorés si le cache est absent.
"""
import copy
import math

import numpy as np
import pytest

from sim import config as C
from sim import environment as E
from sim.config import DATA


def _grille():
    for nom in ("grille_1deg.npz", "grille_2deg.npz", "grille_2deg_partiel.npz"):
        if (DATA / nom).exists():
            return DATA / nom
    return None


pytestmark = pytest.mark.skipif(_grille() is None or not (DATA / "cote.wkb").exists(),
                                reason="cache de données absent (python main.py donnees)")


@pytest.fixture(scope="module")
def env():
    return E.Environnement(_grille())


@pytest.fixture(scope="module")
def cote():
    return E.charger_cote()


@pytest.fixture(scope="module")
def cfg():
    c = C.charger()
    c["solutions"]["S8"] = "validee"
    c["mission"]["max_days"] = 25
    return c


def _run(cfg, env, cote, **kw):
    from sim import run as R
    return R.Simulation(cfg, env, cote, **kw).executer()


@pytest.mark.parametrize("graine,dt", [(0, 600), (1, 600), (2, 1800), (3, 1800)])
def test_vraie_position_toujours_dans_la_boite_sans_saut(cfg, env, cote, graine, dt):
    """Sans fix GPS corrompu, la vraie position doit rester dans la boîte Codac à chaque pas,
    y compris pendant les pertes GPS. Sinon les bornes (vitesse, cap, dérive) sont fausses."""
    c = copy.deepcopy(cfg)
    c["pannes_capteurs"]["gps_saut_par_jour"] = 0.0
    c["pannes_capteurs"]["gps_coupure_par_jour"] = 0.5          # beaucoup de coupures
    r = _run(c, env, cote, graine=graine, dt=dt, modules=dict(risques=False))
    tr = r.traj
    assert (~tr["gps"]).sum() > 0, "le test doit inclure des pertes GPS"
    hors = np.where(~tr["contient"])[0]
    assert len(hors) == 0, (f"BORNES FAUSSES : vraie position hors de la boîte à {len(hors)} pas, "
                            f"premiers jours {[(tr['t'][i] - tr['t'][0]) / 86400 for i in hors[:5]]}")


def test_sorties_de_boite_expliquees_par_sauts_gps(cfg, env, cote):
    """Avec des fix corrompus, une sortie de boîte n'est admise que juste après un saut non détecté."""
    c = copy.deepcopy(cfg)
    c["pannes_capteurs"]["gps_saut_par_jour"] = 1.0
    r = _run(c, env, cote, graine=7, modules=dict(risques=False))
    tr = r.traj
    sauts = np.array(r.stats.get("sauts_t", []))
    for i in np.where(~tr["contient"])[0]:
        t = tr["t"][i]
        assert len(sauts) and ((t - sauts) >= 0).any() and (t - sauts[(t - sauts) >= 0]).min() <= 6 * 3600, \
            f"sortie de boîte à t={t} non expliquée par un saut GPS : bornes fausses"
    assert r.stats["fix_rejetes"] > 0


def test_perte_gps_fait_grandir_la_boite(cfg, env, cote):
    c = copy.deepcopy(cfg)
    c["pannes_capteurs"]["gps_panne_definitive_par_jour"] = 5.0      # GPS HS le premier jour
    r = _run(c, env, cote, graine=3, modules=dict(risques=False))
    tr = r.traj
    assert tr["boite_km"][-1] > 10 * tr["boite_km"][0]
    assert tr["contient"].all()
    assert "degrade" in set(tr["mode"]) or "sans_cap" in set(tr["mode"])


def test_contrefactuel_meme_histoire_avant_divergence(cfg, env, cote):
    """Nombres aléatoires communs : S16 (anti-filets) n'agit qu'à une rencontre de pêche ; avant la
    première rencontre, les deux histoires doivent être identiques à l'événement près.
    (S5, lui, agit aussi en continu via P9 : la trajectoire diverge dès la première mer forte.)"""
    from sim import risks as RK
    reg = RK.charger_registre()
    dens = RK.Densites()
    jeu = RK.tirer_parametres(reg, cfg, 0, dens)
    c0 = copy.deepcopy(cfg)
    c0["mission"]["max_days"] = 60
    c1 = copy.deepcopy(c0)
    c1["solutions"]["S16"] = "validee"
    r0 = _run(c0, env, cote, graine=11, jeu=jeu, densites=dens, registre_yaml=reg)
    r1 = _run(c1, env, cote, graine=11, jeu=jeu, densites=dens, registre_yaml=reg)
    t_div = min([e.t for e in r0.evenements if e.probleme in ("P24", "P23")] + [r0.t_fin_physique, r1.t_fin_physique])
    a = [(e.t, e.type) for e in r0.evenements if e.t < t_div]
    b = [(e.t, e.type) for e in r1.evenements if e.t < t_div]
    assert a == b


def test_priors_beta_coherents():
    from sim import risks as RK
    reg = RK.charger_registre()
    cfg = C.charger()
    vals = [RK.tirer_parametres(reg, cfg, k, None).taux_base["P24"] for k in range(200)]
    # captures : 9,5/30 par mission de 30 j -> ~0,013/j
    assert 0.007 < np.median(vals) < 0.02
    assert np.percentile(vals, 95) > np.percentile(vals, 5) * 1.5      # incertitude non nulle


def test_solution_validee_reduit_le_taux():
    from sim import risks as RK
    from sim.failures import Aleas
    reg = RK.charger_registre()
    cfg = C.charger()
    jeu = RK.tirer_parametres(reg, cfg, 0, None)
    c0, c1 = copy.deepcopy(cfg), copy.deepcopy(cfg)
    c1["solutions"]["S5"] = "validee"
    r0 = RK.Registre(reg, c0, jeu, Aleas(0), None)
    r1 = RK.Registre(reg, c1, jeu, Aleas(0), None)
    assert r1.multiplicateur("P7") < r0.multiplicateur("P7")
    assert r1.multiplicateur("P1") == r0.multiplicateur("P1")
