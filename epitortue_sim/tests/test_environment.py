import numpy as np
import pytest

from sim import environment as E
from sim.geo import ENU, NM, haversine


def test_convention_vent_meteo():
    # vent "de 270°" (d'ouest) souffle vers l'est : u > 0
    u, v = E._uv_depuis(np.array(10.0), np.array(270.0), provenance=True)
    assert u == pytest.approx(10.0) and v == pytest.approx(0.0, abs=1e-9)


def test_convention_courant_oceano():
    # courant "vers 90°" porte à l'est
    u, v = E._uv_depuis(np.array(0.5), np.array(90.0), provenance=False)
    assert u == pytest.approx(0.5) and v == pytest.approx(0.0, abs=1e-9)


def test_interpolation_trilineaire_exacte_sur_champ_lineaire(tmp_path):
    t = np.arange(0, 10 * 3600, 3600, dtype=np.int64)
    lats = np.array([40.0, 42.0, 44.0])
    lons = np.array([-50.0, -48.0, -46.0, -44.0])
    T, LA, LO = np.meshgrid(t, lats, lons, indexing="ij")
    lin = (1e-4 * T + 2 * LA - 3 * LO).astype(np.float32)
    champs = {v: lin for v in E.Environnement.CHAMPS.values()}
    np.savez(tmp_path / "g.npz", t=t, lats=lats, lons=lons, **champs)
    env = E.Environnement(tmp_path / "g.npz")
    r = env.echantillon(12345.0, 41.3, -47.1)
    attendu = 1e-4 * 12345 + 2 * 41.3 - 3 * -47.1
    assert r["hs"] == pytest.approx(attendu, rel=1e-5)
    # rayonnement ERA5 = moyenne de l'heure précédente : lu à t + 30 min (H22)
    assert r["ghi"] == pytest.approx(attendu + 1e-4 * 1800, rel=1e-5)


def test_enu_aller_retour():
    p = ENU(47.0, -48.0)
    x, y = p.vers_local(47.3, -47.5)
    la, lo = p.vers_geo(x, y)
    assert la == pytest.approx(47.3) and lo == pytest.approx(-47.5)
    assert np.hypot(x, y) == pytest.approx(haversine(47, -48, 47.3, -47.5), rel=2e-3)


def test_distance_ligne_depart():
    # H01 : le largage est à >= 40 nm de la ligne de départ (47°W)
    assert haversine(47.0, -48.0, 47.0, -47.0) / NM >= 40.0


def test_poids_open_meteo():
    assert E.poids_requete(10, 9, 31) == pytest.approx(10 * 31 / 14)
    assert E.poids_requete(10, 10, 7) == 10
