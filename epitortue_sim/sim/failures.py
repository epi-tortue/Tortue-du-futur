"""Aléas reproductibles et pannes des capteurs de navigation (GPS, compas).

Nombres aléatoires communs (contrefactuels exacts) :
  chaque processus d'événement a SON flux aléatoire (graine dérivée de son nom) et un seuil
  E ~ Exp(1) tiré à l'avance. On cumule le risque intégré H = ∫ λ(t) dt ; l'événement se
  produit quand H dépasse E. Avec une solution qui divise λ par 10, le même seuil est
  atteint plus tard (ou jamais) : tout le reste de l'histoire est identique.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field

import numpy as np


def flux(graine: int, nom: str) -> np.random.Generator:
    return np.random.default_rng([int(graine) & 0xFFFFFFFF, zlib.crc32(nom.encode())])


class Processus:
    """Processus de Poisson non homogène à seuils pré-tirés (récurrent)."""

    __slots__ = ("nom", "rng", "seuil", "cumul", "n")

    def __init__(self, graine: int, nom: str):
        self.nom = nom
        self.rng = flux(graine, "seuil:" + nom)
        self.seuil = self.rng.exponential()
        self.cumul = 0.0
        self.n = 0

    def avancer(self, taux_par_jour: float, dt_s: float) -> bool:
        if taux_par_jour <= 0:
            return False
        self.cumul += taux_par_jour * dt_s / 86400.0
        if self.cumul >= self.seuil:
            self.cumul -= self.seuil
            self.seuil = self.rng.exponential()
            self.n += 1
            return True
        return False


class Aleas:
    """Registre des processus et des flux de tirages des conséquences."""

    def __init__(self, graine: int):
        self.graine = graine
        self._proc: dict[str, Processus] = {}
        self._flux: dict[str, np.random.Generator] = {}

    def proc(self, nom: str) -> Processus:
        p = self._proc.get(nom)
        if p is None:
            p = self._proc[nom] = Processus(self.graine, nom)
        return p

    def rng(self, nom: str) -> np.random.Generator:
        g = self._flux.get(nom)
        if g is None:
            g = self._flux[nom] = flux(self.graine, "tirage:" + nom)
        return g

    def evenement(self, nom: str, taux_par_jour: float, dt_s: float) -> bool:
        return self.proc(nom).avancer(taux_par_jour, dt_s)


# ---------------------------------------------------------------------------
# Capteurs
# ---------------------------------------------------------------------------
@dataclass
class EtatGPS:
    hs: bool = False                    # panne définitive
    coupure_jusqu: float = -1.0         # fin de coupure temporaire (epoch s)
    n_coupures: int = 0
    n_sauts: int = 0

    def disponible(self, t):
        return (not self.hs) and t >= self.coupure_jusqu


@dataclass
class EtatCompas:
    hs: bool = False                    # gelé sur une valeur
    valeur_gelee: float = 0.0
    biais_deg: float = 0.0
    biais_actif: bool = False
    signe: float = 1.0


@dataclass
class Capteurs:
    cfg: dict
    aleas: Aleas
    gps: EtatGPS = field(default_factory=EtatGPS)
    compas: EtatCompas = field(default_factory=EtatCompas)
    mult_gps: float = 1.0               # modulé par risks (P13/P14/P15/P18, S9/S12/S13)
    mult_compas: float = 1.0

    def pas(self, t, dt_s, evenements: list):
        """Fait évoluer les pannes. Ajoute (type, texte) à `evenements`."""
        p = self.cfg["pannes_capteurs"]
        a = self.aleas
        g, c = self.gps, self.compas
        if not g.hs:
            if a.evenement("gps_hs", p["gps_panne_definitive_par_jour"] * self.mult_gps, dt_s):
                g.hs = True
                evenements.append(("gps_hs", "Panne définitive du GPS"))
            elif t >= g.coupure_jusqu and a.evenement("gps_coupure", p["gps_coupure_par_jour"] * self.mult_gps, dt_s):
                d = p["gps_coupure_duree_mediane_h"] * math.exp(p["gps_coupure_sigma_log"] * a.rng("gps_coupure").normal())
                g.coupure_jusqu = t + d * 3600.0
                g.n_coupures += 1
                evenements.append(("gps_coupure", f"Perte du signal GPS pendant {d:.1f} h"))
        if not c.hs:
            if a.evenement("compas_hs", p["compas_panne_par_jour"] * self.mult_compas, dt_s):
                c.hs = True
                c.valeur_gelee = float(a.rng("compas_hs").uniform(0, 360))
                evenements.append(("compas_hs", f"Panne du compas (valeur figée à {c.valeur_gelee:.0f}°)"))
            elif not c.biais_actif and a.evenement("compas_biais", p["compas_biais_par_jour"] * self.mult_compas, dt_s):
                c.biais_actif = True
                c.signe = 1.0 if a.rng("compas_biais").random() < 0.5 else -1.0
                evenements.append(("compas_biais", "Début d'une dérive lente du compas (biais)"))
        if c.biais_actif and not c.hs:
            c.biais_deg = float(np.clip(c.biais_deg + c.signe * p["compas_biais_deg_par_jour"] * dt_s / 86400.0,
                                        -p["compas_biais_max_deg"], p["compas_biais_max_deg"]))

    def fix_gps(self, t, x, y, dt_s):
        """Fix GPS en coordonnées locales (m) ou None. Bruit gaussien borné + sauts rares."""
        p = self.cfg["pannes_capteurs"]
        if not self.gps.disponible(t):
            return None, False
        rng = self.aleas.rng("gps_bruit")
        sig = self.cfg["bateau"].get("capteurs", {}).get("gps_sigma_m", 15.0)
        r = self.cfg["navigation"]["gps_demi_largeur_m"]
        ex, ey = np.clip(rng.normal(0, sig, 2), -r * 0.99, r * 0.99)
        saut = self.aleas.evenement("gps_saut", p["gps_saut_par_jour"] * self.mult_gps, dt_s)
        if saut:
            lo, hi = p["gps_saut_m"]
            m = math.exp(self.aleas.rng("gps_saut").uniform(math.log(lo), math.log(hi)))
            ang = self.aleas.rng("gps_saut").uniform(0, 2 * math.pi)
            ex, ey = ex + m * math.cos(ang), ey + m * math.sin(ang)
            self.gps.n_sauts += 1
        return (x + ex, y + ey), saut

    def cap_compas(self, cap_vrai_deg):
        """Lecture du compas (°) : vrai cap + biais + bruit ; ou valeur figée si HS."""
        c = self.compas
        if c.hs:
            return c.valeur_gelee
        sig = self.cfg["bateau"].get("capteurs", {}).get("compas_sigma_deg", 3.0)
        b = self.cfg["navigation"]["compas_demi_largeur_deg"]
        bruit = float(np.clip(self.aleas.rng("compas_bruit").normal(0, sig), -b * 0.9, b * 0.9))
        return (cap_vrai_deg + c.biais_deg + bruit) % 360.0
