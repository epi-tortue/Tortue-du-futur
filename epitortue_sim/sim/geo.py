"""Outils géographiques : orthodromie, projection locale ENU, lignes Microtransat."""
from __future__ import annotations

import numpy as np

R_TERRE = 6_371_000.0
NM = 1852.0


def haversine(lat1, lon1, lat2, lon2):
    """Distance orthodromique (m). Accepte des tableaux."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_TERRE * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def cap_initial(lat1, lon1, lat2, lon2):
    """Cap vrai initial (rad, 0 = nord, sens horaire) de 1 vers 2."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    x = np.sin(dl) * np.cos(p2)
    y = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return np.arctan2(x, y) % (2 * np.pi)


def deplacer(lat, lon, de_m, dn_m):
    """Déplacement local (est, nord) en mètres -> nouvelle lat/lon (approx. plane, pas <= qq km)."""
    dlat = dn_m / R_TERRE
    dlon = de_m / (R_TERRE * np.cos(np.radians(lat)))
    return lat + np.degrees(dlat), lon + np.degrees(dlon)


class ENU:
    """Projection locale équirectangulaire recentrable (mètres) autour d'une origine."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = float(lat0), float(lon0)
        self._k = R_TERRE * np.cos(np.radians(self.lat0))

    def vers_local(self, lat, lon):
        x = np.radians(np.asarray(lon) - self.lon0) * self._k
        y = np.radians(np.asarray(lat) - self.lat0) * R_TERRE
        return x, y

    def vers_geo(self, x, y):
        lat = self.lat0 + np.degrees(np.asarray(y) / R_TERRE)
        lon = self.lon0 + np.degrees(np.asarray(x) / self._k)
        return lat, lon


def densifier_ligne(points, pas_deg=0.1):
    """Interpolation linéaire en (lat, lon) entre les sommets (règle D : interpolation linéaire)."""
    out = []
    for (a_lat, a_lon), (b_lat, b_lon) in zip(points[:-1], points[1:]):
        n = max(2, int(np.hypot(b_lat - a_lat, b_lon - a_lon) / pas_deg))
        t = np.linspace(0, 1, n, endpoint=False)
        out.append(np.c_[a_lat + t * (b_lat - a_lat), a_lon + t * (b_lon - a_lon)])
    out.append(np.array([points[-1]]))
    return np.vstack(out)
