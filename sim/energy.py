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


def prevision_solaire(env, cfg: dict, t_s: float, lat: float, lon: float, heures: int = 24) -> np.ndarray:
    """Production moyenne prévue (W) pour chacune des `heures` prochaines heures, à la position actuelle.

    Lit directement les rayonnements réels du cache (direct sur l'horizontale + diffus) : c'est une
    prévision « parfaite » au point où se trouve le bateau [H74]. Même formule que `p_solaire`,
    vectorisée ; le rayonnement d'une heure est lu à t + 30 min [H22], l'angle solaire au milieu de l'heure.
    """
    s = cfg["bateau"]["solaire"]
    t_mid = t_s + 1800.0 + 3600.0 * np.arange(heures)
    ia, fa = env._coins(lat, env.lats[0], env._dla, len(env.lats))
    io, fo = env._coins(lon, env.lons[0], env._dlo, len(env.lons))
    f = np.clip((t_mid + 1800.0 - env.t[0]) / env._dt, 0.0, len(env.t) - 1.0)
    it = np.minimum(f.astype(int), len(env.t) - 2)
    ft = f - it
    i0, i1 = int(it[0]), int(it[-1]) + 2
    bloc = np.asarray(env.P[i0:i1, ia:ia + 2, io:io + 2, :][..., env._irad[1:]], dtype=np.float64)   # dni_h, dhi
    w = np.array([1 - fa, fa])[:, None] * np.array([1 - fo, fo])[None, :]
    serie = np.tensordot(bloc, w, axes=([1, 2], [0, 1]))                    # [temps, 2]
    k = it - i0
    val = serie[k] * (1 - ft)[:, None] + serie[k + 1] * ft[:, None]
    dni_h, dhi = np.maximum(val[:, 0], 0.0), np.maximum(val[:, 1], 0.0)
    # angle zénithal (même algorithme que zenith_rad)
    n = t_mid / 86400.0 + 2440587.5 - 2451545.0
    L = np.radians((280.460 + 0.9856474 * n) % 360)
    g = np.radians((357.528 + 0.9856003 * n) % 360)
    lam = L + math.radians(1.915) * np.sin(g) + math.radians(0.020) * np.sin(2 * g)
    eps = np.radians(23.439 - 0.0000004 * n)
    ra = np.arctan2(np.cos(eps) * np.sin(lam), np.cos(lam))
    dec = np.arcsin(np.sin(eps) * np.sin(lam))
    ha = np.radians(((18.697374558 + 24.06570982441908 * n) % 24) * 15 + lon) - ra
    la = math.radians(lat)
    cz = np.clip(math.sin(la) * np.sin(dec) + math.cos(la) * np.cos(dec) * np.cos(ha), -1.0, 1.0)
    iam = np.where(cz > 0.05, np.maximum(0.0, 1.0 - s["iam_b0"] * (1.0 / np.maximum(cz, 0.05) - 1.0)), 0.0)
    eff = np.where(cz > 0.0, dni_h * iam + dhi * s["iam_diffus"], 0.0)
    return wc(cfg) * s["derating"] * eff / 1000.0


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
        memo = self.__dict__.get("_frac")           # (température, fraction) : inchangé tant que T ne bouge pas
        if memo is not None and memo[0] == self.t_c:
            return memo[1]
        tt, ff = zip(*self.capa_vs_t)
        f = float(np.interp(self.t_c, tt, ff))
        self.__dict__["_frac"] = (self.t_c, f)
        return f

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
    # --- politique « prevision » (S8 validée) [H74] ---
    veille: bool = False            # veille profonde décidée par la politique (électronique endormie)
    regime: str = ""                # "continu" | "economie" (pour le journal et les tests)
    p_plan: float = 0.0             # puissance moteur planifiée (W)
    _prev: np.ndarray | None = None
    _prev_h: int = -1
    _hist: list | None = None       # production réellement mesurée, heure par heure (prévision par persistance)
    _bulletin: tuple | None = None  # (heure de base, prévision sur 27 h pour des panneaux propres)
    _memo_prev: tuple | None = None  # (prévision, consommation, moyenne, heures de jour)

    @property
    def prevision_active(self) -> bool:
        return self.etat_s8 == "validee" and self.cfg["energie"]["validee"].get("politique", "prevision") == "prevision"

    def hotel_veille(self, iridium_ok=True, ais_ok=True) -> float:
        """Consommation en veille profonde : le calculateur dort, l'Iridium se réveille pour la position
        réglementaire, l'AIS et le feu restent allumés si `veille_ais_feu` [H74]."""
        c = self.cfg["bateau"]["consommation"]
        v = self.cfg["energie"]["validee"]
        f = v.get("veille_fraction_calculateur", 0.05)
        p = (c["calculateur_capteurs_w"] + c["divers_w"]) * f
        if iridium_ok:
            p += c["iridium_moyen_w"]
        if ais_ok and v.get("veille_ais_feu", True):
            p += c["ais_feu_w"]
        return p

    def _prevoir(self, env, t, lat, lon, p_pv, facteur_pv, dt_s, parfaite: bool) -> np.ndarray:
        """Production prévue heure par heure sur 24 h (W). Recalculée une fois par heure."""
        h = int(t // 3600)
        if self._hist is None:
            self._hist = []
        if not self._hist or self._hist[-1][0] != h:
            self._hist.append([h, p_pv, 1])
            del self._hist[:-24]
        else:                                           # moyenne de l'heure en cours
            e = self._hist[-1]
            e[1] += (p_pv - e[1]) / (e[2] + 1)
            e[2] += 1
        if self._prev is not None and self._prev_h == h:
            return self._prev
        if env is None:
            prev = np.full(24, self.p_pv_moy)
        elif parfaite or len(self._hist) < 24:
            # la prévision du jour du largage est connue ; ensuite, selon l'option.
            # Le bulletin (27 h) est rafraîchi toutes les 3 h : on en lit la tranche des 24 h à venir.
            b = self._bulletin
            if b is None or not (0 <= h - b[0] < 3):
                b = self._bulletin = (h, prevision_solaire(env, self.cfg, h * 3600.0, lat, lon, 27))
            prev = b[1][h - b[0]:h - b[0] + 24] * facteur_pv
        else:
            # persistance : demain ressemblera à aujourd'hui (ce que le bateau peut faire seul)
            prev = np.array([x[1] for x in self._hist[-24:]])
        self._prev, self._prev_h = prev, h
        return prev

    def planifier(self, env, t, lat, lon, bat, p_pv, facteur_pv, dt_s, iridium_ok=True, ais_ok=True,
                  reception_ok=True):
        """Politique « prevision » : décide la veille de nuit et la puissance moteur [H74].

        Principe : on prévoit le solaire des 24 h suivantes.
          - régime « continu » (assez de soleil pour faire tourner le moteur jour et nuit) : loi de régulation
            d'origine, alimentée par la moyenne PRÉVUE au lieu de la moyenne passée ;
          - régime « économie » (hiver) : le jour, moteur avec tout ce que la batterie contient au-delà de
            la réserve nécessaire à l'électronique de nuit ; la nuit, veille profonde (pas de black-out,
            pas de redémarrage, la position réglementaire continue de partir).
        """
        v = self.cfg["energie"]["validee"]
        prop = self.cfg["bateau"]["propulsion"]
        parfaite = v.get("prevision", "donnees") == "donnees" and reception_ok
        prev = self._prevoir(env, t, lat, lon, p_pv, facteur_pv, dt_s, parfaite)
        self.delestage = 1 if bat.soc < v["delestage_1_soc"] else 0
        h_actif = self.charge_hotel(iridium_ok, ais_ok, True)
        h_veille = self.hotel_veille(iridium_ok, ais_ok)
        cap = bat.cap_eff
        e_dispo = max(0.0, bat.e_wh - bat.e_plancher() - v.get("reserve_soc", 0.05) * cap) * bat.eta_d
        # grandeurs tirées de la prévision horaire : recalculées seulement quand la prévision ou la
        # consommation change (deux pas sur trois les réutilisent ; mêmes opérations numpy, mêmes valeurs)
        memo = self._memo_prev
        if memo is None or memo[0] is not prev or memo[1] != h_actif:
            memo = self._memo_prev = (prev, h_actif, float(prev.mean()), (prev >= h_actif).tolist())
        moy, jour = memo[2], memo[3]
        p_cont = moy * bat.eta_c - h_actif                         # puissance moteur soutenable en continu
        # jour[i] : le soleil prévu couvre l'électronique pendant l'heure i
        nuit_restante = 0                                          # heures avant que le soleil ne couvre l'électronique
        while nuit_restante < 24 and not jour[nuit_restante]:
            nuit_restante += 1
        # régime continu : assez de soleil prévu ET assez de batterie pour tenir éveillé jusqu'au jour
        if p_cont >= v.get("seuil_continu_w", 8.0) and e_dispo >= h_actif * nuit_restante:
            self.regime, self.veille = "continu", False
            p = p_cont + (bat.soc - v["soc_cible"]) * self.cfg["bateau"]["batterie"]["capacite_wh"] / v["constante_temps_h"]
            self.p_plan = float(min(max(p, 0.0), v["p_max_w"])) if bat.soc >= v["delestage_2_soc"] else 0.0
            return
        self.regime = "economie"
        h_dt = dt_s / 3600.0
        p_min = v.get("p_min_utile_w", prop["p_croisiere_w"])
        if p_pv >= h_actif or jour[0]:
            # --- jour : dépenser l'excédent d'ici la nuit, en gardant la réserve de veille
            n_j = 0
            while n_j < 24 and jour[n_j]:
                n_j += 1
            n_j = max(n_j, 1)
            n_n = 0
            while n_j + n_n < 24 and not jour[n_j + n_n]:
                n_n += 1
            reserve = h_veille * n_n / bat.eta_d * v.get("marge_reserve", 1.2)
            apport = float(np.clip(prev[:n_j] - h_actif, 0.0, None).sum()) * bat.eta_c
            budget = e_dispo + apport - reserve
            p = budget / n_j
            self.veille = False
            # ce que la batterie peut fournir pendant CE pas sans passer sous la réserve de sécurité
            # (le soleil prévu pour plus tard dans la journée n'est pas encore là)
            p_possible = max(0.0, e_dispo / h_dt + p_pv - h_actif)
            if p >= p_min:
                self.p_plan = float(min(p, v["p_max_w"], p_possible))
            elif e_dispo - reserve >= p_min * h_dt:                # rafale à la puissance utile
                self.p_plan = float(min(p_min, p_possible))
            else:
                self.p_plan = 0.0
            return
        # --- nuit
        n_n = 0
        while n_n < 24 and not jour[n_n]:
            n_n += 1
        n_n = max(n_n, 1)
        p = (e_dispo - h_actif * n_n) / n_n                        # moteur possible en restant éveillé
        if p >= p_min:
            self.veille, self.p_plan = False, float(min(p, v["p_max_w"]))
        else:
            self.veille, self.p_plan = True, 0.0

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
        if v.get("politique", "prevision") == "prevision":
            return 0.0 if self.veille else self.p_plan * fraction_mode
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
