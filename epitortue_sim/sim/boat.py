"""Modèle physique du bateau : bilan de forces 2D quasi-statique.

Coque : coque finale epi-tortue/Testa (outputs/optim.json, 13/09/2026). Les grandeurs
hydrostatiques sont recopiées dans config.yaml (bateau.coque) ; la résistance de carène
reprend exactement les formules de Testa (coque/propulsion.py, régime déplacement) :

    R_carène(V) = (1 + k) · ½ρ S V² Cf(Re)  +  M g r_h · x/(1+x)
        Cf = 0,075 / (log10 Re − 2)²       (ITTC-57)
        k  = Watanabe(Cb, Lwl/Bwl, Bwl/T)  borné [0 ; 0,5]
        x  = c_v · Fnv⁴ / r_h,  Fnv = V / √(g ∇^(1/3))   (vague forfaitaire, c_v=0,008, r_h=0,20)

Le pas de temps (10 min) est long devant les transitoires : on résout l'équilibre.

Repère bateau : x vers l'avant (cap ψ), y sur tribord.
  Axe x :  T(u_x, P) + F_air,x − R_carène(u_x) − R_vagues(Hs, α) = 0
  Axe y :  F_air,y − ½ ρ Cd_lat A_lat |u_y| u_y = 0                   (pas de quille : dérive)
  T = min(η_prop·η_chaîne·P / u_x ,  T_statique)   T_statique = (2 ρ A_hélice P_arbre²)^(1/3)
  F_air = ½ ρ_air Cd A(dir) |a| a,  a = vent à hauteur de pont − vitesse fond du bateau
  vent à hauteur de pont = facteur_profil · U10                        [H18]
  R_vagues = k_w · g(α) · Hs²,  g = 0,6 + 0,4 cos α (1 de face, 0,2 de l'arrière) [H13]
Vitesse fond = u (eau) + courant réel [H04].
"""
from __future__ import annotations

import math
from dataclasses import dataclass

RHO = 1025.0
RHO_AIR = 1.225
NU = 1.19e-6
G = 9.81


@dataclass
class Coque:
    L: float
    M: float
    S: float
    Lwl: float
    Bwl: float
    T: float
    Cb: float
    volume: float
    eta_prop: float
    eta_chaine: float
    a_front: float
    a_cote: float
    cd_air_front: float
    cd_air_cote: float
    a_lat_eau: float
    cd_lat_eau: float
    d_helice: float
    p_max: float
    k_vagues: float = 0.0
    c_vague: float = 0.008
    r_hump: float = 0.20

    @property
    def eta(self):
        return self.eta_prop * self.eta_chaine

    @property
    def k_forme(self):
        k = -0.095 + 25.6 * self.Cb / ((self.Lwl / self.Bwl) ** 2 * math.sqrt(self.Bwl / self.T))
        return min(max(k, 0.0), 0.5)

    def r_carene(self, v, encrassement=0.0):
        """Résistance eau calme [N] (impaire en v pour la marche arrière/dérive)."""
        va = abs(v)
        if va < 1e-9:
            return 0.0
        re = max(va * self.Lwl / NU, 1e5)
        cf = 0.075 / (math.log10(re) - 2.0) ** 2
        rf = 0.5 * RHO * self.S * va * va * cf * (1.0 + encrassement)
        fnv = va / math.sqrt(G * self.volume ** (1.0 / 3.0))
        x = self.c_vague * fnv ** 4 / self.r_hump
        rw = self.M * G * self.r_hump * x / (1.0 + x)
        return math.copysign((1.0 + self.k_forme) * rf + rw, v)

    def poussee(self, u, p_elec):
        if p_elec <= 0:
            return 0.0
        p_arbre = self.eta_chaine * p_elec
        a_h = math.pi * self.d_helice ** 2 / 4
        t_stat = (2 * RHO * a_h * p_arbre ** 2) ** (1.0 / 3.0)
        return min(self.eta * p_elec / max(u, 1e-3), t_stat)

    def p_pour_vitesse_calme(self, v):
        return self.r_carene(v) * v / self.eta

    @classmethod
    def depuis_config(cls, cfg: dict) -> "Coque":
        c = cfg["bateau"]["coque"]
        a = cfg["bateau"]["aero"]
        p = cfg["bateau"]["propulsion"]
        co = cls(L=c["L"], M=c["M"], S=c["S"], Lwl=c["Lwl"], Bwl=c["Bwl"], T=c["T"], Cb=c["Cb"],
                 volume=c["volume"], eta_prop=p["rendement_helice"], eta_chaine=p["rendement_chaine"],
                 a_front=a["a_front_m2"], a_cote=a["a_cote_m2"], cd_air_front=a["cd_front"],
                 cd_air_cote=a["cd_cote"], a_lat_eau=a["a_lat_eau_m2"], cd_lat_eau=a["cd_lat_eau"],
                 d_helice=p["diametre_helice_m"], p_max=p["p_max_w"])
        # calage des vagues : à la puissance qui donne v_ref en eau calme, Hs_moitie de face -> v_ref/2
        v0 = p["vagues_v_ref_ms"]
        p0 = co.p_pour_vitesse_calme(v0)
        v1, hs = v0 / 2, p["perte_vagues_hs_moitie_m"]
        co.k_vagues = (co.eta * p0 / v1 - co.r_carene(v1)) / hs ** 2
        return co


def facteur_angle_vagues(cap_rad, dir_propagation_u, dir_propagation_v):
    """g(α) : 1 si le bateau fait face aux vagues, 0,2 s'il les a dans le dos."""
    n = math.hypot(dir_propagation_u, dir_propagation_v)
    if n < 1e-6:
        return 0.6
    cos_suivi = (math.sin(cap_rad) * dir_propagation_u + math.cos(cap_rad) * dir_propagation_v) / n
    return 0.6 - 0.4 * cos_suivi


def _resoudre_axe(co: Coque, p, f_air_x, r_vagues, encr):
    """u_x racine de f(u) = T(u) + F_air,x − R(u) − R_vagues·tanh(u/0,2) (f décroissante -> bissection).

    La résistance ajoutée par les vagues n'existe que si le bateau avance par rapport à l'eau
    (tanh : pas de discontinuité en 0, et aucun effet sur la dérive pure)."""
    t0 = co.poussee(1e-3, p) if p > 0 else 0.0

    def f(u):
        t = co.poussee(u, p) if u > 1e-3 else t0
        return t + f_air_x - co.r_carene(u, encr) - r_vagues * math.tanh(u / 0.2)
    lo, hi = -4.0, 5.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return lo if abs(flo) < abs(fhi) else hi
    while hi - lo > 2e-3:
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def equilibre(co: Coque, p_elec, cap, vent_u, vent_v, courant_u, courant_v, hs, vdir_u, vdir_v,
              encrassement=0.0, facteur_profil=0.72):
    """Vitesse surface (u_x, u_y) en axes bateau et vitesse fond (est, nord).

    Si P = 0, le cap imposé est ignoré (bateau en travers au vent)."""
    p = min(max(p_elec, 0.0), co.p_max)
    if p <= 0.0:
        # moteur coupé : le bateau (sans quille, pod à l'arrière) se met en travers au vent [H23]
        cap = math.atan2(vent_u, vent_v) + math.pi / 2 if (vent_u or vent_v) else cap
    sx, cx = math.sin(cap), math.cos(cap)        # axe avant (est, nord)
    yx, yy = cx, -sx                              # axe tribord
    wu, wv = facteur_profil * vent_u, facteur_profil * vent_v
    r_v = co.k_vagues * facteur_angle_vagues(cap, vdir_u, vdir_v) * hs * hs
    ux, uy = 0.0, 0.0
    for _ in range(3):
        gu = ux * sx + uy * yx + courant_u
        gv = ux * cx + uy * yy + courant_v
        au, av = wu - gu, wv - gv                 # vent apparent (vers où l'air pousse)
        ax, ay = au * sx + av * cx, au * yx + av * yy
        na = math.hypot(ax, ay)
        fx = 0.5 * RHO_AIR * co.cd_air_front * co.a_front * na * ax
        fy = 0.5 * RHO_AIR * co.cd_air_cote * co.a_cote * na * ay
        ux = _resoudre_axe(co, p, fx, r_v, encrassement)
        uy = math.copysign(math.sqrt(abs(fy) / (0.5 * RHO * co.cd_lat_eau * co.a_lat_eau)), fy)
    gu = ux * sx + uy * yx + courant_u
    gv = ux * cx + uy * yy + courant_v
    return ux, uy, gu, gv


def encrassement(sst, cfg: dict, cumul_prec: float, dt_jours: float) -> float:
    """Cumul de la traînée de frottement additionnelle (fraction). x3 en eau > 18 °C. [H15]"""
    b = cfg["bateau"]
    taux = b["biofouling_par_mois"] / 30.0
    if sst > 18.0:
        taux *= b["biofouling_facteur_eau_chaude"]
    return cumul_prec + taux * dt_jours
