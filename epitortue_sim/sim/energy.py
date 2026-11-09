"""Énergie : production solaire réelle (ERA5), batterie LiFePO4 thermique, chauffage, gestion S8.

Production (pont plat, cf. doc « simulation solaire » : le plat est optimal en pire cas) :
    P_pv = Wc · D · [ DNI_h · IAM_ASHRAE(θz) + DHI · IAM_diffus ] / 1000
  - DNI_h, DHI : rayonnement direct (sur l'horizontale) et diffus ERA5, réels, à la position ;
  - θz : angle zénithal (formule NOAA rapide, vérifiée contre pvlib dans les tests) ;
  - Wc = surface de cellules (coque Testa) × rendement [H19] ; D = 0,70 (doc).

Batterie :
  - énergie stockée E (Wh, nominale 480 Wh) ; capacité accessible réduite par le froid (P11) ;
  - charge interdite sous 0 °C, limitée à 0,1 C entre 0 et 5 °C, 0,5 C au-dessus [H20] ;
  - température : premier ordre vers T_env = SST + Δ (Δ = 2 °C [H16]), constante de temps C/G ;
  - chauffage (B2) : jusqu'à P_max, pour tenir la consigne, alimenté par le surplus solaire
    (mode « quand_soleil ») ou en permanence (« toujours »).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

CAPA_THERMIQUE_J_PAR_K = 8.0 * 1000.0   # 8 kg de cellules × ~1000 J/(kg·K) [H17]


def zenith_rad(t_s: float, lat: float, lon: float) -> float:
    """Angle zénithal du soleil (rad). Algorithme NOAA/Michalsky simplifié (~0,01°)."""
    n = t_s / 86400.0 + 2440587.5 - 2451545.0
    L = math.radians((280.460 + 0.9856474 * n) % 360)
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst_h = (18.697374558 + 24.06570982441908 * n) % 24
    ha = math.radians(gmst_h * 15 + lon) - ra
    la = math.radians(lat)
    cz = math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha)
    return math.acos(max(-1.0, min(1.0, cz)))


def iam_ashrae(theta, b0=0.05):
    c = math.cos(theta)
    if c <= 0.05:
        return 0.0
    return max(0.0, 1.0 - b0 * (1.0 / c - 1.0))


def p_solaire(cfg: dict, t_s, lat, lon, dni_h, dhi, facteur_panneaux=1.0) -> float:
    s = cfg["bateau"]["solaire"]
    wc = cfg["bateau"]["coque"]["surface_panneaux_m2"] * 1000.0 * s["rendement_cellules"]
    dni_h, dhi = max(dni_h, 0.0), max(dhi, 0.0)
    if dni_h + dhi <= 0:
        return 0.0
    z = zenith_rad(t_s, lat, lon)
    if z >= math.pi / 2:
        return 0.0
    eff = dni_h * iam_ashrae(z, s["iam_b0"]) + dhi * s["iam_diffus"]
    return wc * s["derating"] * eff / 1000.0 * facteur_panneaux


def wc(cfg) -> float:
    return cfg["bateau"]["coque"]["surface_panneaux_m2"] * 1000.0 * cfg["bateau"]["solaire"]["rendement_cellules"]


@dataclass
class Batterie:
    cap_wh: float
    e_wh: float
    t_c: float
    eta_c: float
    eta_d: float
    t_min: float
    t_pleine: float
    capa_vs_t: list
    c_froid: float = 0.1
    c_max: float = 0.5
    facteur_sante: float = 1.0      # P11 : perte de capacité (charge à froid, cellule HS)
    bms_coupe: bool = False

    @classmethod
    def depuis_config(cls, cfg, t_init):
        b = cfg["bateau"]["batterie"]
        return cls(cap_wh=b["capacite_wh"], e_wh=b["capacite_wh"] * b["soc_initial"], t_c=t_init,
                   eta_c=b["rendement_charge"], eta_d=b["rendement_decharge"], t_min=b["t_charge_min_c"],
                   t_pleine=b["t_charge_pleine_c"], capa_vs_t=b["capacite_vs_t"])

    @property
    def cap_eff(self):
        return self.cap_wh * self.facteur_sante

    def fraction_accessible(self):
        tt, ff = zip(*self.capa_vs_t)
        return float(np.interp(self.t_c, tt, ff))

    def e_plancher(self):
        """Énergie inaccessible à cause du froid (réversible)."""
        return self.cap_eff * (1.0 - self.fraction_accessible())

    @property
    def soc(self):
        """SOC « vu par le BMS » : fraction de l'énergie accessible."""
        acc = self.cap_eff - self.e_plancher()
        return max(0.0, min(1.0, (self.e_wh - self.e_plancher()) / max(acc, 1e-6)))

    def limite_charge_w(self, interdire_froid=True):
        if self.t_c < self.t_min:
            return 0.0 if interdire_froid else self.c_max * self.cap_wh
        if self.t_c < self.t_pleine:
            return self.c_froid * self.cap_wh
        return self.c_max * self.cap_wh

    def echanger(self, p_net_w, dt_s, interdire_froid=True):
        """p_net > 0 : charge ; < 0 : décharge. Retourne (p_absorbee, p_ecretee, charge_a_froid)."""
        h = dt_s / 3600.0
        if p_net_w >= 0:
            lim = self.limite_charge_w(interdire_froid)
            p_in = min(p_net_w, lim)
            place = (self.cap_eff - self.e_wh) / (self.eta_c * h) if h > 0 else 0
            p_in = max(0.0, min(p_in, place))
            self.e_wh += p_in * self.eta_c * h
            froid = (self.t_c < self.t_min) and p_in > 0
            return p_in, p_net_w - p_in, froid
        besoin = -p_net_w / self.eta_d * h
        dispo = self.e_wh - self.e_plancher()
        if besoin <= dispo:
            self.e_wh -= besoin
            return p_net_w, 0.0, False
        self.e_wh = max(self.e_plancher(), self.e_wh - dispo)
        self.bms_coupe = True
        return -dispo * self.eta_d / h if h > 0 else 0.0, 0.0, False

    def thermique(self, t_env, p_chauffe, g_w_k, dt_s):
        """Premier ordre : C dT/dt = G (T_env − T) + P_chauffe (intégration exacte)."""
        t_eq = t_env + p_chauffe / g_w_k
        tau = CAPA_THERMIQUE_J_PAR_K / g_w_k
        self.t_c = t_eq + (self.t_c - t_eq) * math.exp(-dt_s / tau)


def puissance_chauffage(cfg, bat: Batterie, t_env, surplus_w) -> float:
    ch = cfg["bateau"]["batterie"]["chauffage"]
    if not ch["active"]:
        return 0.0
    g = ch["conductance_w_par_k"]
    besoin = max(0.0, g * (ch["consigne_c"] - t_env))
    # rattrapage si la batterie est sous la consigne (on vise la consigne en ~1 constante de temps)
    besoin += max(0.0, (ch["consigne_c"] - bat.t_c)) * CAPA_THERMIQUE_J_PAR_K / (6 * 3600.0)
    p = min(besoin, ch["puissance_max_w"])
    if ch["mode"] == "quand_soleil":
        p = min(p, max(0.0, surplus_w))
    return p


# ---------------------------------------------------------------------------
# Gestion d'énergie (S8) : consommations et puissance moteur
# ---------------------------------------------------------------------------
@dataclass
class GestionEnergie:
    etat_s8: str
    cfg: dict
    p_pv_moy: float = 0.0           # moyenne glissante 24 h de la production
    delestage: int = 0              # 0 normal, 1 délestage léger, 2 veille (dérive)

    def charge_hotel(self, iridium_ok=True, ais_ok=True, calculateur_actif=True):
        c = self.cfg["bateau"]["consommation"]
        p = 0.0
        if calculateur_actif:
            p += c["calculateur_capteurs_w"] * (0.35 if self.delestage >= 2 else 1.0)
        if iridium_ok:
            p += c["iridium_moyen_w"] * (0.5 if self.delestage >= 1 else 1.0)
        if ais_ok:
            p += c["ais_feu_w"] * (0.5 if self.delestage >= 1 else 1.0)
        p += c["divers_w"]
        return p

    def maj_moyenne(self, p_pv, dt_s):
        a = dt_s / (24 * 3600.0)
        self.p_pv_moy += a * (p_pv - self.p_pv_moy)

    def p_moteur(self, soc, p_hotel, fraction_mode=1.0, p_pv=None):
        prop = self.cfg["bateau"]["propulsion"]
        e = self.cfg["energie"]
        if self.etat_s8 == "absente":
            self.delestage = 0
            return prop["p_croisiere_w"] * fraction_mode
        if self.etat_s8 == "partielle":
            self.delestage = 0
            for smin, frac in e["paliers_partielle"]:
                if soc >= smin:
                    return prop["p_croisiere_w"] * frac * fraction_mode
            return 0.0
        v = e["validee"]
        self.delestage = 2 if soc < v["delestage_2_soc"] else (1 if soc < v["delestage_1_soc"] else 0)
        cap = self.cfg["bateau"]["batterie"]["capacite_wh"]
        # Veille de nuit quand l'énergie manque (hiver) : électronique en veille et moteur coupé la nuit,
        # le moteur consomme le surplus solaire le jour (doc P12 : « couper le moteur la nuit »)  [H24]
        veille = v.get("veille_nuit", True) and self.p_pv_moy < v.get("seuil_veille_w", 15.0)
        if veille and p_pv is not None:
            if p_pv <= 0.5:
                self.delestage = max(self.delestage, 2)
                return 0.0
            p = p_pv - p_hotel + (soc - v["soc_cible"]) * cap / v.get("constante_temps_jour_h", 6.0)
            return float(np.clip(p, 0.0, v["p_max_w"])) * fraction_mode if self.delestage < 2 else 0.0
        if self.delestage >= 2:
            return 0.0
        p = self.p_pv_moy - p_hotel + (soc - v["soc_cible"]) * cap / v["constante_temps_h"]
        return float(np.clip(p, 0.0, v["p_max_w"])) * fraction_mode
