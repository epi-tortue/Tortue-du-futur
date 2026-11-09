import copy
import math
from datetime import datetime, timezone

import numpy as np
import pytest

from sim import boat as B
from sim import config as C
from sim import energy as EN


@pytest.fixture(scope="module")
def cfg():
    return C.charger()


@pytest.fixture(scope="module")
def coque(cfg):
    return B.Coque.depuis_config(cfg)


def test_polaire_testa(coque):
    # reproduit coque/propulsion.py de Testa (hors fardage) : 1,60 Wh/km à 1 m/s
    p = coque.p_pour_vitesse_calme(1.0)
    assert p * 1000 / 1.0 / 3600 == pytest.approx(1.60, abs=0.02)
    assert coque.p_pour_vitesse_calme(1.5) == pytest.approx(21.1, abs=0.3)


def test_equilibre_calme(coque):
    ux, uy, gu, gv = B.equilibre(coque, 21.1, math.radians(90), 0, 0, 0, 0, 0, 0, 0, 0.0)
    assert ux == pytest.approx(1.5, abs=0.02) and abs(uy) < 1e-6
    assert gu == pytest.approx(ux, abs=1e-6)


def test_vagues_calage(coque, cfg):
    # Hs = 4 m de face divise par 2 la vitesse de référence (H13)
    p0 = coque.p_pour_vitesse_calme(1.5)
    ux, *_ = B.equilibre(coque, p0, math.radians(90), 0, 0, 0, 0, 4.0, -1.0, 0.0, 0.0)
    assert ux == pytest.approx(0.75, abs=0.03)


def test_vent_de_face_ralentit(coque):
    v0 = B.equilibre(coque, 21, math.radians(90), 0, 0, 0, 0, 0, 0, 0, 0.0)[0]
    v1 = B.equilibre(coque, 21, math.radians(90), -15, 0, 0, 0, 0, 0, 0, 0.0)[0]
    assert v1 < 0.6 * v0


def test_derive_moteur_coupe_travers(coque):
    # moteur coupé : en travers au vent, dérive de quelques % du vent (sans quille)
    _, _, gu, gv = B.equilibre(coque, 0, 0.0, 0, 10.0, 0, 0, 0, 0, 0, 0.0, 0.72)
    v = math.hypot(gu, gv)
    assert 0.02 * 10 < v < 0.06 * 10
    assert gv > 0          # poussé sous le vent (vers le nord)


def test_courant_additif(coque):
    # sans vent, le bateau suit le courant (au vent apparent près : l'air immobile le freine un peu)
    _, _, gu, gv = B.equilibre(coque, 0, 0.0, 0, 0, 0.3, -0.2, 0, 0, 0, 0.0)
    assert (gu, gv) == pytest.approx((0.3, -0.2), abs=0.04)


def test_zenith_contre_pvlib():
    pvlib = pytest.importorskip("pvlib")
    import pandas as pd
    ts = pd.date_range("2026-01-01", "2026-07-01", freq="7D3h", tz="UTC")
    sp = pvlib.solarposition.get_solarposition(ts, 50.0, -30.0)
    for t, z in zip(ts, sp["apparent_zenith"]):
        mine = math.degrees(EN.zenith_rad(t.timestamp(), 50.0, -30.0))
        if z < 85:
            assert mine == pytest.approx(z, abs=0.6)   # réfraction ignorée


def test_solaire_nul_la_nuit(cfg):
    t = datetime(2026, 1, 1, 3, tzinfo=timezone.utc).timestamp()  # nuit à 30°W
    assert EN.p_solaire(cfg, t, 50, -30, 100.0, 50.0) == 0.0


def test_batterie_pas_de_charge_sous_zero(cfg):
    b = EN.Batterie.depuis_config(cfg, -2.0)
    b.e_wh = 100
    p_in, p_ecr, froid = b.echanger(50.0, 3600, interdire_froid=True)
    assert p_in == 0 and p_ecr == 50.0 and not froid
    p_in, _, froid = b.echanger(50.0, 3600, interdire_froid=False)
    assert p_in > 0 and froid            # sans verrou BMS (S6 absente) : charge à froid


def test_batterie_charge_limitee_entre_0_et_5(cfg):
    b = EN.Batterie.depuis_config(cfg, 3.0)
    b.e_wh = 100
    p_in, _, _ = b.echanger(200.0, 600)
    assert p_in == pytest.approx(0.1 * 480)


def test_conservation_energie(cfg):
    b = EN.Batterie.depuis_config(cfg, 15.0)
    b.e_wh = 200
    e0 = b.e_wh
    p_in, _, _ = b.echanger(40.0, 3600)
    assert b.e_wh - e0 == pytest.approx(p_in * b.eta_c)
    e1 = b.e_wh
    b.echanger(-30.0, 3600)
    assert e1 - b.e_wh == pytest.approx(30.0 / b.eta_d)


def test_blackout(cfg):
    b = EN.Batterie.depuis_config(cfg, 15.0)
    b.e_wh = 1.0
    b.echanger(-100.0, 3600)
    assert b.bms_coupe and b.soc == pytest.approx(0.0, abs=1e-9)


def test_chauffage_regime_permanent(cfg):
    c = copy.deepcopy(cfg)
    c["bateau"]["batterie"]["chauffage"]["active"] = True
    c["bateau"]["batterie"]["chauffage"]["mode"] = "toujours"
    b = EN.Batterie.depuis_config(c, 2.0)
    g = c["bateau"]["batterie"]["chauffage"]["conductance_w_par_k"]
    for _ in range(200):
        p = EN.puissance_chauffage(c, b, 2.0, 100.0)
        b.thermique(2.0, p, g, 600)
    assert b.t_c == pytest.approx(6.0, abs=0.3)          # consigne tenue
    assert p == pytest.approx(g * 4.0, abs=0.3)         # P = G·(T_consigne − T_env)


def test_gestion_validee_respecte_soc(cfg):
    g = EN.GestionEnergie("validee", cfg)
    g.p_pv_moy = 10.0
    assert g.p_moteur(0.10, 4.75) == 0.0 and g.delestage == 2
    assert g.p_moteur(0.9, 4.75) > g.p_moteur(0.5, 4.75)
