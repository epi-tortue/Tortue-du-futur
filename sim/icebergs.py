"""Risque iceberg (hors P1–P28). Désactivé par défaut : aucune donnée n'est inventée [H08] [H77].

Le module ne s'active que si `donnees.icebergs.active` est vrai ET si le fichier d'observations
existe. Format exact de `data/icebergs.csv` (UTF-8, séparateur virgule, une ligne d'en-tête) :

    date,lat,lon,taille
    2026-04-12,47.85,-48.20,M
    2026-04-12T14:30:00Z,46.10,-47.55,GR

    date    date ou date-heure ISO 8601 de l'observation (UTC)
    lat     latitude en degrés décimaux, nord positif
    lon     longitude en degrés décimaux, est positif (donc négative en Atlantique Ouest)
    taille  facultatif ; classe de taille de l'International Ice Patrol :
            GR growler, BB bergy bit, S small, M medium, L large, VL very large ; vide = inconnue (M)

Modèle : autour du bateau, on compte les icebergs observés dans un rayon `rayon_km` et dans une
fenêtre de ± `fenetre_jours` ; cette densité (icebergs/km²) × la largeur de choc (longueur de
l'iceberg) × la distance parcourue donne un taux de collision, comme pour les navires (P22).
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .config import RACINE
from .geo import haversine

# Longueur caractéristique (m) par classe de taille. Bornes des classes : International Ice Patrol
# (growler < 5 m, bergy bit 5–14 m, small 15–60 m, medium 61–120 m, large 121–200 m, very large > 200 m) ;
# on prend le milieu de chaque classe [H77].
LONGUEUR_M = {"GR": 3.0, "BB": 10.0, "S": 40.0, "M": 90.0, "L": 160.0, "VL": 250.0}
COLONNES = ("date", "lat", "lon")


class Icebergs:
    def __init__(self, t: np.ndarray, lat: np.ndarray, lon: np.ndarray, longueur: np.ndarray, prm: dict):
        self.t, self.lat, self.lon, self.longueur = t, lat, lon, longueur
        self.rayon_m = float(prm.get("rayon_km", 100.0)) * 1000.0
        self.fenetre_s = float(prm.get("fenetre_jours", 15.0)) * 86400.0
        self.gravite = prm.get("gravite", {"coule": 0.5, "voie_eau": 0.4, "sans_degat": 0.1})

    @classmethod
    def depuis_config(cls, cfg: dict) -> "Icebergs | None":
        """None si le module est désactivé. Erreur explicite s'il est activé sans données valides."""
        prm = cfg.get("donnees", {}).get("icebergs", {}) or {}
        if not prm.get("active", False):
            return None
        f = Path(prm.get("fichier", "data/icebergs.csv"))
        f = f if f.is_absolute() else RACINE / f
        if not f.exists():
            raise FileNotFoundError(f"Icebergs activés mais {f} est absent. Voir le README (format et source "
                                    "des données) ou mettre donnees.icebergs.active à false.")
        return cls(*lire_csv(f), prm)

    def densite_km2(self, t_s: float, lat: float, lon: float) -> tuple[float, float]:
        """(icebergs par km², longueur moyenne en m) autour du bateau."""
        sel = np.abs(self.t - t_s) <= self.fenetre_s
        if not sel.any():
            return 0.0, 0.0
        d = haversine(lat, lon, self.lat[sel], self.lon[sel])
        pres = d <= self.rayon_m
        n = int(pres.sum())
        if n == 0:
            return 0.0, 0.0
        return n / (np.pi * (self.rayon_m / 1000.0) ** 2), float(self.longueur[sel][pres].mean())

    def taux_collision_par_jour(self, t_s: float, lat: float, lon: float, v_fond_ms: float) -> float:
        rho, longueur = self.densite_km2(t_s, lat, lon)
        return rho * (longueur / 1000.0) * (max(v_fond_ms, 0.0) * 86.4)      # km parcourus par jour


def lire_csv(chemin: Path):
    """Lit et valide data/icebergs.csv. Retourne (t [s], lat, lon, longueur [m])."""
    t, la, lo, lg = [], [], [], []
    with open(chemin, encoding="utf-8", newline="") as fh:
        lecteur = csv.DictReader(fh)
        manque = [c for c in COLONNES if c not in (lecteur.fieldnames or [])]
        if manque:
            raise ValueError(f"{chemin} : colonnes manquantes {manque} (attendu : date,lat,lon[,taille])")
        for i, ligne in enumerate(lecteur, start=2):
            try:
                d = datetime.fromisoformat(ligne["date"].strip().replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                a, b = float(ligne["lat"]), float(ligne["lon"])
            except (ValueError, AttributeError) as e:
                raise ValueError(f"{chemin}, ligne {i} : {e}") from e
            if not (-90 <= a <= 90 and -180 <= b <= 180):
                raise ValueError(f"{chemin}, ligne {i} : position hors limites ({a}, {b})")
            taille = (ligne.get("taille") or "M").strip().upper() or "M"
            if taille not in LONGUEUR_M:
                raise ValueError(f"{chemin}, ligne {i} : taille {taille!r} inconnue (attendu {sorted(LONGUEUR_M)})")
            t.append(d.timestamp())
            la.append(a)
            lo.append(b)
            lg.append(LONGUEUR_M[taille])
    return np.array(t), np.array(la), np.array(lo), np.array(lg)
