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

from dataclasses import dataclass, field

import numpy as np

from .geo import cap_initial, haversine


@dataclass
class Autopilote:
    waypoints: list[tuple[float, float]]
    rayon_wp_m: float = 25_000.0
    i_wp: int = 0
    journal: list[str] = field(default_factory=list)

    @classmethod
    def depuis_config(cls, cfg: dict) -> "Autopilote":
        a = cfg["mission"]["arrivee"]
        wps = [tuple(w) for w in cfg.get("autopilote", {}).get("waypoints", [])]
        wps.append((a["lat"], a["lon"]))
        return cls(waypoints=wps, rayon_wp_m=a["rayon_km"] * 1000.0)

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
    ux, uy = np.sin(route), np.cos(route)          # unitaire le long de la route
    nx, ny = uy, -ux                               # normale (à droite)
    d_n = du * nx + dv * ny                        # dérive transversale
    s = np.clip(-d_n / v, -1.0, 1.0)               # composante transversale du cap
    c = np.sqrt(1.0 - s * s)                       # composante longitudinale (>= 0)
    hx, hy = c * ux + s * nx, c * uy + s * ny
    return float(np.arctan2(hx, hy) % (2 * np.pi))
