"""Autopilote simplifié inspiré d'ArduPilot (mode AUTO, rover/bateau).

- Suit une liste de waypoints (par défaut : directement le centre du cercle d'arrivée),
  par orthodromie recalculée depuis la *position estimée* (jamais la vraie).
- Compense la dérive estimée (courant + fardage) : on choisit le cap ψ tel que la
  vitesse fond soit colinéaire à la route désirée (« crabe »). Si la dérive
  transversale dépasse la vitesse surface, on annule autant que possible la dérive
  transversale (on remonte le courant).
- Les modes dégradés (perte GPS, gouvernail, énergie) s'ajoutent aux étapes 3–6.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .geo import cap_initial, deplacer, haversine


@dataclass
class Autopilote:
    waypoints: list[tuple[float, float]]
    rayon_wp_m: float = 25_000.0
    i_wp: int = 0
    journal: list[str] = field(default_factory=list)
    approche: dict = field(default_factory=dict)        # stratégie d'approche du cercle [H75]
    derive_lissee: tuple = (0.0, 0.0)                    # dérive estimée, lissée (m/s, est et nord)

    @classmethod
    def depuis_config(cls, cfg: dict) -> "Autopilote":
        a = cfg["mission"]["arrivee"]
        wps = [tuple(w) for w in cfg.get("autopilote", {}).get("waypoints", [])]
        wps += [tuple(w) for w in cfg.get("navigation", {}).get("waypoints", []) or []]
        wps.append((a["lat"], a["lon"]))
        return cls(waypoints=wps, rayon_wp_m=a["rayon_km"] * 1000.0,
                   approche=dict(cfg.get("navigation", {}).get("approche", {}) or {}))

    def cible(self):
        return self.waypoints[self.i_wp]

    def maj_waypoint(self, lat_est, lon_est):
        while self.i_wp < len(self.waypoints) - 1:
            la, lo = self.waypoints[self.i_wp]
            if haversine(lat_est, lon_est, la, lo) < self.rayon_wp_m:
                self.i_wp += 1
                self.journal.append(f"waypoint {self.i_wp} atteint")
            else:
                break

    def cible_guidage(self, lat_est, lon_est, derive_u=0.0, derive_v=0.0, v_ref=1.0, dt_s=0.0):
        """Point à viser. Hors du dernier waypoint, c'est le waypoint ; pour le cercle d'arrivée, la
        stratégie d'approche s'applique [H75] :

          centre    : le centre du cercle (comportement d'origine) ;
          bord_sud  : un point au sud du centre (fraction_rayon × rayon), DÉCALÉ EN AMONT de la dérive
                      estimée : décalage = −dérive lissée × temps de trajet restant × gain, borné par
                      decalage_max_km et par la moitié de la distance restante. Le bateau arrive ainsi
                      par le côté d'où vient la dérive, qui le porte dans le cercle au lieu de l'en écarter.
        """
        la, lo = self.cible()
        ap = self.approche
        if self.i_wp < len(self.waypoints) - 1 or ap.get("strategie", "centre") == "centre":
            return la, lo
        # dérive lissée (la fenêtre de 2 h de l'estimateur est trop bruitée pour une stratégie)
        tau = ap.get("lissage_derive_h", 24.0) * 3600.0
        a = min(1.0, dt_s / tau) if tau > 0 else 1.0
        du, dv = self.derive_lissee
        self.derive_lissee = (du + a * (derive_u - du), dv + a * (derive_v - dv))
        la_s, lo_s = deplacer(la, lo, 0.0, -ap.get("fraction_rayon", 0.6) * self.rayon_wp_m)
        dist = float(haversine(lat_est, lon_est, la_s, lo_s))
        if dist > ap.get("distance_activation_km", 400.0) * 1000.0:
            return float(la_s), float(lo_s)
        du, dv = self.derive_lissee
        t_reste = dist / max(v_ref, 0.3)
        g = ap.get("gain_derive", 1.0)
        ox, oy = -du * t_reste * g, -dv * t_reste * g
        n = float(np.hypot(ox, oy))
        lim = min(ap.get("decalage_max_km", 150.0) * 1000.0, 0.5 * dist)
        if n > lim > 0:
            ox, oy = ox * lim / n, oy * lim / n
        la_c, lo_c = deplacer(la_s, lo_s, ox, oy)
        return float(la_c), float(lo_c)

    def consigne_cap(self, lat_est, lon_est, v_surface, derive_u, derive_v):
        """Retourne (cap à tenir [rad], route désirée [rad])."""
        self.maj_waypoint(lat_est, lon_est)
        la, lo = self.cible()
        route = float(cap_initial(lat_est, lon_est, la, lo))
        return cap_crabe(route, v_surface, derive_u, derive_v), route


def cap_crabe(route, v, du, dv):
    """Cap ψ tel que v·[sin ψ, cos ψ] + d soit dirigé selon `route`."""
    if v <= 1e-6:
        return route
    ux, uy = math.sin(route), math.cos(route)      # unitaire le long de la route
    nx, ny = uy, -ux                               # normale (à droite)
    d_n = float(du) * nx + float(dv) * ny          # dérive transversale
    s = min(max(-d_n / v, -1.0), 1.0)              # composante transversale du cap
    c = math.sqrt(1.0 - s * s)                     # composante longitudinale (>= 0)
    hx, hy = c * ux + s * nx, c * uy + s * ny
    return float(math.atan2(hx, hy) % (2 * np.pi))
