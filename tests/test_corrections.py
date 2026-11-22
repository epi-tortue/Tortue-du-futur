"""Un test par correction du modèle (phase « limites connues »).

Les tests marqués `donnees` rejouent la météo réelle en cache ; ils sont ignorés si le cache est absent.
"""
import copy
import math

import numpy as np
import pytest

from sim import config as C
from sim import energy as EN
from sim import environment as E
from sim import risks as RK
from sim.autopilot import Autopilote
from sim.config import DATA
from sim.failures import Aleas
from sim.geo import haversine

GRILLE = DATA / "grille_2deg.npz"
donnees = pytest.mark.skipif(not GRILLE.exists() or not (DATA / "cote.wkb").exists(),
                             reason="cache de données absent (python main.py donnees)")


@pytest.fixture(scope="module")
def cfg():
    return C.charger()


@pytest.fixture(scope="module")
def reg():
    return RK.charger_registre()


@pytest.fixture(scope="module")
def env():
    return E.Environnement(GRILLE)


@pytest.fixture(scope="module")
def cote():
    return E.charger_cote()


def _registre(reg, cfg, **sur):
    c = copy.deepcopy(cfg)
    if sur:
        c["registre_surcharges"] = sur
    r = RK.registre_pour(c, reg)
    return RK.Registre(r, c, RK.tirer_parametres(r, c, 0, None), Aleas(0), None)


# ------------------------------------------------------------------ 1. chavirage [H71]
def test_chavirage_depend_de_la_periode_et_de_l_exposition(reg, cfg):
    R = _registre(reg, cfg)
    prm = reg["problemes"]["P2"]["chavirage"]
    ref = dict(hs=prm["hs_ref_m"], tp=prm["t_ref_s"], exposition=1.0)
    assert R.facteur_chavirage(ref) == pytest.approx(1.0)                 # calé sur l'état de référence
    courte = R.facteur_chavirage(dict(hs=4.0, tp=8.0, exposition=1.0))
    longue = R.facteur_chavirage(dict(hs=4.0, tp=11.0, exposition=1.0))
    assert courte > 1.0 > longue                                           # mer courte et cambrée > houle longue
    assert longue == 0.0                                                   # sous le seuil de déferlement
    # à hauteur et période égales, en travers est plus dangereux que face ou dos à la vague
    assert R.facteur_chavirage(dict(hs=3.0, tp=8.0, exposition=1.0)) > \
        R.facteur_chavirage(dict(hs=3.0, tp=8.0, exposition=0.0)) > 0
    # une mer plate ne chavire personne, et il n'y a plus de seuil brutal à 3 m
    assert R.facteur_chavirage(dict(hs=0.3, tp=3.0, exposition=1.0)) < 1e-3
    assert R.facteur_chavirage(dict(hs=2.9, tp=7.0, exposition=1.0)) > 0


def test_chavirage_ancien_modele_conserve(reg, cfg):
    R = _registre(reg, cfg, problemes={"P2": {"chavirage": {"modele": "hs4"}}})
    assert R.facteur_chavirage(dict(hs=2.9, tp=7.0, exposition=1.0)) == 0.0
    assert R.facteur_chavirage(dict(hs=8.0, tp=7.0, exposition=1.0)) == pytest.approx(16.0)


def test_redressement_depend_de_la_stabilite(reg, cfg):
    c = copy.deepcopy(cfg)
    c["solutions"]["S1"] = "validee"
    testa = RK.Registre(reg, c, RK.tirer_parametres(reg, c, 0, None), Aleas(0), None)
    assert testa.proba_redressement(False) == pytest.approx(0.97)          # Testa : AVS 180°, rien ne change
    c2 = copy.deepcopy(c)
    c2["bateau"]["coque"]["stabilite"]["AVS_deg"] = 135                    # variante avec une position retournée stable
    variante = RK.Registre(reg, c2, RK.tirer_parametres(reg, c2, 0, None), Aleas(0), None)
    assert variante.proba_redressement(False) == pytest.approx(0.97 * 0.5)
    assert testa.proba_redressement(True) == pytest.approx(0.30)           # drains bouchés (P25)


# ------------------------------------------------------------------ 2. P9 [H72]
def test_p9_lacet_ne_recompte_pas_la_resistance_des_vagues(reg):
    p9 = reg["problemes"]["P9"]
    assert p9["modele"] == "lacet"
    pertes = {e: 1 - RK.facteur_lacet(s) for e, s in p9["lacet_sigma_deg"].items()}
    assert pertes["absente"] > pertes["partielle"] > pertes["validee"] > 0
    # la perte de pilotage est géométrique et bornée : très en dessous de l'ancienne (25 % sur la puissance au cube)
    assert pertes["absente"] < 0.12 and pertes["validee"] < 0.02
    assert RK.facteur_lacet(0.0) == 1.0                                    # barre parfaite : aucune perte ajoutée


@donnees
def test_p9_mer_plate_aucune_perte_et_vagues_dans_boat(cfg, env, cote):
    """La résistance des vagues vit dans boat.equilibre (pour tous) ; P9 n'ajoute qu'un facteur de route."""
    from sim import boat as B
    co = B.Coque.depuis_config(cfg)
    v_calme = B.equilibre(co, 21, math.radians(90), 0, 0, 0, 0, 0.0, -1, 0)[0]
    v_vagues = B.equilibre(co, 21, math.radians(90), 0, 0, 0, 0, 4.0, -1, 0)[0]
    assert v_vagues < 0.6 * v_calme                                        # effet physique, sans P9
    assert RK.facteur_lacet(25.0 * min(1.0, 0.0 / 4.0)) == 1.0             # Hs = 0 : σ = 0, pas de perte de pilotage


# ------------------------------------------------------------------ 3. gestion d'énergie S8 [H74]
def test_prevision_solaire_coherente_avec_p_solaire(cfg, tmp_path):
    t = np.arange(0, 72 * 3600, 3600, dtype=np.int64) + 1767225600          # 2026-01-01 00:00 UTC
    lats, lons = np.array([46.0, 48.0]), np.array([-50.0, -48.0])
    champs = {v: np.full((len(t), 2, 2), 200.0, dtype=np.float32) for v in E.Environnement.CHAMPS.values()}
    np.savez(tmp_path / "g.npz", t=t, lats=lats, lons=lons, **champs)
    env = E.Environnement(tmp_path / "g.npz")
    prev = EN.prevision_solaire(env, cfg, float(t[0]), 47.0, -49.0)
    attendu = [EN.p_solaire(cfg, float(t[0]) + 1800 + 3600 * h, 47.0, -49.0, 200.0, 200.0) for h in range(24)]
    assert prev == pytest.approx(attendu, abs=1e-6)
    assert prev.max() > 20 and prev.min() == 0.0                           # du soleil à midi, rien la nuit


def test_politique_prevision_dort_la_nuit_sans_vider_la_batterie(cfg):
    c = copy.deepcopy(cfg)
    g = EN.GestionEnergie("validee", c)
    bat = EN.Batterie.depuis_config(c, 10.0)
    bat.e_wh = 60.0
    prev = np.array([0.0] * 14 + [30.0] * 8 + [0.0] * 2)                   # nuit de 14 h puis 8 h de soleil faible
    g._prev, g._prev_h, g._hist = prev, 0, [[0, 0.0, 1]]
    g.planifier(None, 0.0, 47.0, -48.0, bat, 0.0, 1.0, 1800)
    assert g.regime == "economie" and g.veille and g.p_moteur(bat.soc, 0.0) == 0.0
    # le jour : le moteur tourne, mais la réserve de la nuit suivante est conservée
    jour = np.array([30.0] * 8 + [0.0] * 16)
    g._prev = jour
    g.planifier(None, 0.0, 47.0, -48.0, bat, 30.0, 1.0, 1800)
    assert not g.veille and g.p_plan > 0
    reserve = g.hotel_veille() * 16 / bat.eta_d
    apport = (30.0 - g.charge_hotel()) * 8 * bat.eta_c
    assert g.p_plan * 8 <= (bat.e_wh - bat.e_plancher()) * bat.eta_d + apport - reserve + 1e-6
    # été : assez de soleil prévu -> régime continu, pas de veille
    bat.e_wh = 400.0
    g._prev = np.array([0.0] * 6 + [120.0] * 16 + [0.0] * 2)
    g.planifier(None, 0.0, 47.0, -48.0, bat, 0.0, 1.0, 1800)
    assert g.regime == "continu" and not g.veille and g.p_plan > 0


def test_ancienne_politique_s8_conservee(cfg):
    c = copy.deepcopy(cfg)
    c["energie"]["validee"]["politique"] = "regulation"
    g = EN.GestionEnergie("validee", c)
    g.p_pv_moy = 10.0
    assert not g.prevision_active
    assert g.p_moteur(0.10, 4.75) == 0.0 and g.delestage == 2
    assert g.p_moteur(0.9, 4.75) > g.p_moteur(0.5, 4.75)


@donnees
def test_prevision_au_moins_aussi_bien_que_naive_et_que_l_ancienne(cfg, env, cote):
    """Ensemble de largages d'hiver (navigation parfaite, sans pannes) : la politique « prevision » ne fait
    jamais de black-out, avance plus que l'ancienne régulation, et autant que la naïve à 5 % près — alors que
    la naïve passe ses nuits en black-out (silence radio, redémarrages)."""
    from types import SimpleNamespace

    from sim import analyse_energie as AE
    ctx = SimpleNamespace(env=env, cote=cote)
    res = AE.comparer(cfg, ctx, "2026-01-01T12:00:00Z", ["naive", "regulation", "prevision"], n=4, pas_h=24.0,
                      jour_mesure=20, max_days=21)
    assert res["prevision"]["blackouts"] == 0 and res["naive"]["blackouts"] > 10
    assert res["prevision"]["reste_nm"] < res["regulation"]["reste_nm"]
    fait = lambda r: 1272.0 - r["reste_nm"]  # noqa: E731   distance gagnée vers l'arrivée
    assert fait(res["prevision"]) >= 0.95 * fait(res["naive"])


# ------------------------------------------------------------------ 4. pêche [H73]
def test_facteur_de_rencontre_configurable(reg, cfg):
    ctx = dict(peche=2.0)
    r1 = _registre(reg, cfg)
    r2 = _registre(reg, cfg, rencontres={"facteur_rencontre": 2.0})
    assert r1.taux_rencontre_peche(ctx) > 0
    assert r2.taux_rencontre_peche(ctx) == pytest.approx(2.0 * r1.taux_rencontre_peche(ctx))


@donnees
def test_route_de_reference_fixe_le_calage_de_la_peche(reg, cfg):
    dens = RK.Densites()
    cotiere = copy.deepcopy(cfg)
    cotiere["mission"]["depart"] = {"lat": 49.0, "lon": -8.5}
    cotiere["mission"]["arrivee"]["lat"], cotiere["mission"]["arrivee"]["lon"] = 47.0, -48.0
    libre = RK.tirer_parametres(reg, cotiere, 0, dens)
    c2 = copy.deepcopy(cotiere)
    c2["registre_surcharges"] = {"calibration": {"route_reference": {"depart": cfg["mission"]["depart"],
                                                                      "arrivee": cfg["mission"]["arrivee"]}}}
    fixe = RK.tirer_parametres(RK.registre_pour(c2, reg), c2, 0, dens)
    nominal = RK.tirer_parametres(reg, cfg, 0, dens)
    assert fixe.densite_ref == pytest.approx(nominal.densite_ref)          # calage inchangé
    assert libre.densite_ref != pytest.approx(nominal.densite_ref)         # sans cela, recalé sur la côte


# ------------------------------------------------------------------ 5. approche [H75]
def test_approche_bord_sud_decalee_en_amont_de_la_derive(cfg):
    a = cfg["mission"]["arrivee"]
    c = copy.deepcopy(cfg)
    c["navigation"]["approche"]["strategie"] = "centre"
    assert Autopilote.depuis_config(c).cible_guidage(51.0, -20.0, 0.3, 0.3, 1.0, 1800) == (a["lat"], a["lon"])
    ap = Autopilote.depuis_config(cfg)
    la, lo = ap.cible_guidage(47.0, -40.0, 0.0, 0.0, 1.0, 1800)            # loin : bord sud, sans décalage
    assert lo == pytest.approx(a["lon"]) and la < a["lat"]
    d_centre = haversine(la, lo, a["lat"], a["lon"])
    assert d_centre == pytest.approx(0.6 * a["rayon_km"] * 1000, rel=1e-3) and d_centre < a["rayon_km"] * 1000
    for _ in range(200):                                                   # dérive établie vers le nord-est
        la2, lo2 = ap.cible_guidage(51.5, -18.5, 0.3, 0.3, 0.8, 1800)
    assert la2 < la and lo2 < lo                                           # point visé déplacé au sud-ouest (amont)
    dist = haversine(51.5, -18.5, la, lo)
    assert haversine(la2, lo2, la, lo) <= 0.51 * dist                      # décalage borné (≤ moitié de la distance)
    for _ in range(200):                                                   # sans dérive, retour au bord sud
        la3, lo3 = ap.cible_guidage(51.5, -18.5, 0.0, 0.0, 0.8, 1800)
    assert (la3, lo3) == pytest.approx((la, lo), abs=0.05)             # lissage sur 24 h : reste 1,5 % du décalage


# ------------------------------------------------------------------ 6. marge GPS [H34]
@donnees
def test_marge_gps_compromis_garantie_precision(cfg, env, cote):
    """Avec des sauts GPS fréquents : sans marge, la vraie position sort de la boîte ; avec une marge égale
    au plus grand saut, elle n'en sort plus jamais, mais la boîte après un fix est plus large de 2 × marge."""
    from sim import run as R
    saut_max = cfg["pannes_capteurs"]["gps_saut_m"][1]
    assert cfg["navigation"]["gps_marge_saut_m"] >= saut_max                # le défaut couvre tous les sauts modélisés
    hors, largeur = {}, {}
    for marge in (0.0, 1000.0, float(saut_max)):
        c = copy.deepcopy(cfg)
        c["solutions"]["S8"] = "validee"
        c["energie"]["validee"]["politique"] = "regulation"                 # pas de veille : on isole le GPS
        c["mission"]["max_days"] = 20
        c["pannes_capteurs"]["gps_saut_par_jour"] = 3.0
        c["navigation"]["gps_marge_saut_m"] = marge
        r = R.Simulation(c, env, cote, graine=7, dt=1800, modules=dict(risques=False)).executer()
        hors[marge] = int((~r.traj["contient"]).sum())
        largeur[marge] = float(np.median(r.traj["boite_km"]))
        assert r.stats["sauts_gps"] > 20
    assert hors[0.0] > 0                                                    # garantie perdue sans marge
    assert hors[float(saut_max)] == 0                                       # garantie tenue
    assert hors[1000.0] <= hors[0.0]
    assert largeur[0.0] < largeur[1000.0] < largeur[float(saut_max)]        # prix : la précision
    assert largeur[float(saut_max)] - largeur[0.0] == pytest.approx(2 * saut_max / 1000, rel=0.3)


# ------------------------------------------------------------------ 7. plusieurs années [H76]
def test_periodes_et_noms_des_annees(cfg, monkeypatch):
    monkeypatch.setattr(E, "fin_donnees", lambda c: "2026-11-02")
    assert E.periode_annee(cfg, 2026) == ("2026-01-01", "2026-11-02")
    assert E.periode_annee(cfg, 2024) == ("2024-01-01", "2024-12-31")
    with pytest.raises(ValueError):
        E.periode_annee(cfg, 2027)
    g = cfg["donnees"]["grille"]
    assert E.nom_grille(g, 2026, cfg) == "grille_2deg.npz"
    assert E.nom_grille(g, 2024, cfg) == "grille_2deg_2024.npz"


@donnees
def test_peche_autre_annee_meme_mois(cfg):
    from datetime import datetime, timezone
    d = RK.Densites()
    t26 = datetime(2026, 6, 15, tzinfo=timezone.utc).timestamp()
    t24 = datetime(2024, 6, 15, tzinfo=timezone.utc).timestamp()
    assert d._idx(47.0, -47.0, t24) == d._idx(47.0, -47.0, t26)            # juin 2024 -> pêche de juin 2026


# ------------------------------------------------------------------ 8. icebergs [H77]
def test_icebergs_desactives_par_defaut_et_format(cfg, tmp_path):
    from sim.icebergs import Icebergs, lire_csv
    assert Icebergs.depuis_config(cfg) is None
    f = tmp_path / "icebergs.csv"
    f.write_text("date,lat,lon,taille\n2026-04-12,47.5,-47.5,M\n2026-04-12T14:30:00Z,47.6,-47.4,GR\n",
                 encoding="utf-8")
    c = copy.deepcopy(cfg)
    c["donnees"]["icebergs"].update(active=True, fichier=str(f))
    ice = Icebergs.depuis_config(c)
    t = lire_csv(f)[0][0]
    assert ice.taux_collision_par_jour(t, 47.5, -47.5, 1.0) > 0
    assert ice.taux_collision_par_jour(t, 52.0, -20.0, 1.0) == 0.0          # loin des glaces
    assert ice.taux_collision_par_jour(t + 90 * 86400, 47.5, -47.5, 1.0) == 0.0   # hors saison
    c["donnees"]["icebergs"]["fichier"] = str(tmp_path / "absent.csv")
    with pytest.raises(FileNotFoundError):
        Icebergs.depuis_config(c)                                           # activé sans données : erreur, rien d'inventé
    f.write_text("date,lat\n2026-04-12,47.5\n", encoding="utf-8")
    with pytest.raises(ValueError):
        lire_csv(f)


# ------------------------------------------------------------------ 9. grille à 1°
def test_choix_de_la_grille(cfg):
    c = copy.deepcopy(cfg)
    c["simulation"]["grille"] = "2deg"
    f2 = E.chemin_grille(c, strict=False)
    assert f2 is None or f2.name == "grille_2deg.npz"
    c["simulation"]["grille"] = "auto"
    fa = E.chemin_grille(c, strict=False)
    if (DATA / "grille_1deg.npz").exists():
        assert fa.name == "grille_1deg.npz"                                 # la grille fine est bien celle utilisée
    c["simulation"]["grille"] = "3deg"
    with pytest.raises(ValueError):
        E.chemin_grille(c)


def test_decomposition_meteo_modele():
    """[H76] Années différentes et jeux identiques : l'écart-type « météo » retrouve l'écart entre années,
    et l'écart-type « modèle » reste proche de zéro (et inversement)."""
    import random

    from sim.annees import composantes
    rnd = random.Random(0)

    def runs(p_annee, p_jeu):
        return [{"jeu": j, "fin": "arrivee" if rnd.random() < p_annee * p_jeu[j] else "x"}
                for j in range(25) for _ in range(40)]
    plat = [1.0] * 25
    c = composantes({2024: runs(0.2, plat), 2025: runs(0.5, plat), 2026: runs(0.8, plat)})
    assert 0.2 < c["sd_meteo"] < 0.4 and c["sd_modele"] < 0.05
    jeux = [0.4 + 1.2 * (j % 2) for j in range(25)]           # moitié des jeux à 0,2, moitié à 0,8
    c = composantes({a: runs(0.5, jeux) for a in (2024, 2025, 2026)})
    assert c["sd_meteo"] < 0.05 and 0.2 < c["sd_modele"] < 0.4
