"""Registre des risques P1–P28 : taux, modulation par l'environnement réel, effet des
solutions S1–S20, tirages reproductibles et cascades explicites.

Ce module calcule *quand* un problème survient. La transition d'état correspondante
(« conséquence ») est appliquée par sim/run.py, qui possède l'état du bateau.

Incertitude : chaque Monte-Carlo tire `jeux_parametres` jeux de paramètres (taux de base,
multiplicateurs) dans leurs priors ; un jeu est partagé par tous les contrefactuels.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from .config import DATA, RACINE
from .failures import Aleas, flux
from .geo import haversine

ETATS = ("absente", "partielle", "validee")
CONSEQUENCES_FIN = {
    "arrivee": "Arrivée dans le cercle",
    "capture": "Récupéré par un pêcheur / un navire",
    "perdu_filet": "Perdu, pris dans un engin de pêche",
    "coule": "Coulé",
    "echouement": "Échoué à la côte",
    "chavire": "Chaviré sans se redresser",
    "panne_energie": "Panne d'énergie définitive",
    "sans_propulsion": "Sans propulsion (dérive)",
    "sans_gouverne": "Sans gouverne (dérive)",
    "calculateur": "Calculateur figé",
    "disqualification": "Disqualifié (silence > 10 j ou > 15 j cumulés)",
    "navigation": "Perdu (navigation impossible)",
    "fin_donnees": "Toujours en mer à la fin des données",
    "hors_domaine": "Sorti de la zone simulée",
}


def charger_registre(chemin: Path | None = None) -> dict:
    with open(chemin or RACINE / "risks.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _lognormal(rng, med, f90):
    if f90 <= 1.0 or med <= 0:
        return float(med)
    sigma = math.log(f90) / 1.645
    return float(med * math.exp(sigma * rng.normal()))


# ---------------------------------------------------------------------------
# Densités GFW (pêche, trafic)
# ---------------------------------------------------------------------------
class Densites:
    def __init__(self):
        z = np.load(DATA / "gfw.npz")
        self.mois = [str(m) for m in z["mois"]]
        self.lats, self.lons = z["lats"], z["lons"]
        self.peche = z["peche_h_km2"]
        self.commerce = z["commerce_h_km2"]
        self.pas = float(self.lats[1] - self.lats[0])

    def _idx(self, lat, lon, t_s):
        from datetime import datetime, timezone
        m = datetime.fromtimestamp(t_s, timezone.utc).strftime("%Y-%m")
        k = self.mois.index(m) if m in self.mois else (0 if m < self.mois[0] else len(self.mois) - 1)
        i = int(round((lat - self.lats[0]) / self.pas))
        j = int(round((lon - self.lons[0]) / self.pas))
        if 0 <= i < len(self.lats) and 0 <= j < len(self.lons):
            return k, i, j
        return None

    def peche_h_km2(self, lat, lon, t_s):
        ix = self._idx(lat, lon, t_s)
        return float(self.peche[ix]) if ix else 0.0

    def commerce_h_km2(self, lat, lon, t_s):
        ix = self._idx(lat, lon, t_s)
        return float(self.commerce[ix]) if ix else 0.0

    def moyenne_route(self, cfg, distance_km, n=60):
        """Effort de pêche moyen (annuel) sur les `distance_km` premiers km de l'orthodromie."""
        d, a = cfg["mission"]["depart"], cfg["mission"]["arrivee"]
        tot = haversine(d["lat"], d["lon"], a["lat"], a["lon"]) / 1000.0
        f = min(1.0, distance_km / tot)
        la1, lo1, la2, lo2 = map(math.radians, (d["lat"], d["lon"], a["lat"], a["lon"]))
        dd = tot / 6371.0
        vals = []
        P = self.peche.mean(axis=0)
        for s in np.linspace(0, f, n):
            A, B = math.sin((1 - s) * dd) / math.sin(dd), math.sin(s * dd) / math.sin(dd)
            x = A * math.cos(la1) * math.cos(lo1) + B * math.cos(la2) * math.cos(lo2)
            y = A * math.cos(la1) * math.sin(lo1) + B * math.cos(la2) * math.sin(lo2)
            z = A * math.sin(la1) + B * math.sin(la2)
            lat, lon = math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))
            i = int(round((lat - self.lats[0]) / self.pas))
            j = int(round((lon - self.lons[0]) / self.pas))
            if 0 <= i < len(self.lats) and 0 <= j < len(self.lons):
                vals.append(P[i, j])
        return float(np.mean(vals)) if vals else 1e-3


# ---------------------------------------------------------------------------
# Paramètres tirés (un jeu = une réalisation de l'incertitude épistémique)
# ---------------------------------------------------------------------------
@dataclass
class JeuParametres:
    indice: int
    taux_base: dict                  # Pi -> taux/jour (état « partielle » = historique)
    mult: dict                       # (Pi, Sj, état) -> multiplicateur
    globaux: dict                    # ("S13"|"S20", état) -> multiplicateur
    taux_rencontre_ref: float        # rencontres de pêche / jour à la densité de référence
    densite_ref: float


def tirer_parametres(reg: dict, cfg: dict, indice: int, densites: Densites | None) -> JeuParametres:
    rng = flux(1000 + indice, "parametres")
    cal = reg["calibration"]
    taux, mult = {}, {}
    familles = {}
    for fam in ("captures", "logiciel", "mecanique"):
        k, n = cal[fam]
        p = rng.beta(k + 0.5, n - k + 0.5)
        familles[fam] = -math.log(1 - p) / cal["exposition_j"]
    for pid, P in reg["problemes"].items():
        t = P["taux"]
        if "comptage" in t:
            # les comptages historiques sont des FINS de mission : taux d'occurrence = taux de fin / P(fin | Pi)
            taux[pid] = familles[t["comptage"]] * t["part"] / t.get("p_fin_partielle", 1.0)
        else:
            taux[pid] = _lognormal(rng, t["mediane"], t["facteur90"])
        mdef = reg["multiplicateurs_defaut"]
        for j, s in enumerate(P["solutions"]):
            for e in ETATS:
                med, f = (P.get("mult") or mdef)[e]
                m = _lognormal(rng, med, f)
                if j > 0:
                    m = m ** reg.get("secondaires_exposant", 0.5)
                mult[(pid, s, e)] = m
    glob = {}
    for cle, sol in (("validation_globale", "S13"), ("demarche_progressive", "S20")):
        for e in ETATS:
            glob[(sol, e)] = _lognormal(rng, *reg[cle][e])
    # pêche : la famille « captures » (fin de mission) = rencontres × proba de fin par rencontre
    P24, P23 = reg["problemes"]["P24"], reg["problemes"]["P23"]
    iss, eng = P24["issues"], P24["engagement_issue"]
    p_fin = iss["recupere"] * (1 - P23["laisse"]["partielle"]) + iss["engagement"] * (eng["capture"] + eng["perdu"])
    taux_rencontre = taux["P24"] / p_fin
    dref = 1.0
    if densites is not None:
        dist = cal["vitesse_ref_ms"] * 86400 * cal["exposition_j"] / 1000.0
        dref = densites.moyenne_route(cfg, dist)
    return JeuParametres(indice, taux, mult, glob, taux_rencontre, dref)


# ---------------------------------------------------------------------------
# Registre en cours de run
# ---------------------------------------------------------------------------
@dataclass
class Cascade:
    t: float
    pid: str
    cause: str
    condition: str | None = None


@dataclass
class Registre:
    reg: dict
    cfg: dict
    jeu: JeuParametres
    aleas: Aleas
    densites: Densites | None
    cascades: list = field(default_factory=list)
    occurrences: dict = field(default_factory=dict)       # Pi -> nombre
    premiere: dict = field(default_factory=dict)          # Pi -> t
    incidents_recents: list = field(default_factory=list)

    def etat(self, s):
        return self.cfg["solutions"].get(s, "absente")

    def multiplicateur(self, pid) -> float:
        P = self.reg["problemes"][pid]
        m = 1.0
        for s in P["solutions"]:
            m *= self.jeu.mult[(pid, s, self.etat(s))]
        if P["domaine"] in self.reg["validation_globale"]["domaines"]:
            m *= self.jeu.globaux[("S13", self.etat("S13"))]
        if P["domaine"] in self.reg["demarche_progressive"]["domaines"]:
            m *= self.jeu.globaux[("S20", self.etat("S20"))]
        return m

    def param(self, pid, cle):
        """Paramètre dépendant de l'état de la solution principale du problème."""
        P = self.reg["problemes"][pid]
        val = P[cle]
        if isinstance(val, dict) and set(val) >= set(ETATS):
            return val[self.etat(P["solutions"][0])]
        return val

    def param_solution(self, pid, cle, solution):
        return self.reg["problemes"][pid][cle][self.etat(solution)]

    # ------------------------------------------------------------------
    def taux(self, pid, ctx) -> float:
        P = self.reg["problemes"][pid]
        mod = P["modulateur"]
        base = self.jeu.taux_base[pid]
        if base <= 0:
            return 0.0
        hs = ctx["hs"]
        if mod == "aucun":
            f = 1.0
        elif mod == "hs_cube":
            f = (hs / 4.0) ** 3
        elif mod == "chavirage":
            f = (hs / 4.0) ** 4 if hs > 3.0 else 0.0
        elif mod == "moteur":
            f = 1.0 if ctx["p_moteur"] > 0 else 0.0
        elif mod == "debris":
            f = (1.0 + ctx["peche"] / max(self.jeu.densite_ref, 1e-6)) if ctx["p_moteur"] > 0 else 0.0
        elif mod == "cycles_barre":
            f = (1.0 + hs / 2.0) if ctx["barre_active"] else 0.0
        elif mod == "vieillissement":
            j = max(ctx["jours"], 0.0)
            f = 2.5 * (j / 30.0) ** 1.5           # Weibull k = 2,5 : λ(t) ∝ t^1,5, normalisé à 30 j
        elif mod == "imprevu":
            f = 1.0 + len(self.incidents_recents)
        elif mod == "redemarrages":
            f = 1.0 + 0.2 * min(ctx["redemarrages"], 20)        # plafonné à ×5 [H62]
        elif mod in ("peche", "collision"):
            return 0.0                             # traités à part (rencontres)
        else:
            raise ValueError(f"modulateur inconnu {mod}")
        if not ctx["calculateur_actif"] and P["domaine"] in ("F",):
            return 0.0
        return base * f * self.multiplicateur(pid)

    def taux_rencontre_peche(self, ctx) -> float:
        m = self.jeu.mult[("P24", "S19", self.etat("S19"))]
        return self.jeu.taux_rencontre_ref * ctx["peche"] / max(self.jeu.densite_ref, 1e-9) * m

    def taux_collision(self, ctx) -> float:
        r = self.reg["rencontres"]
        rho = ctx["commerce"] / 730.0                     # navires / km² (présence moyenne)
        par_h = rho * 2 * r["largeur_collision_m"] / 1000.0 * r["vitesse_navire_kmh"]
        evit = r["evitement_ais"][self.etat("S15")]
        return par_h * 24.0 * (1 - evit) * self.multiplicateur("P22")

    # ------------------------------------------------------------------
    def pas(self, t, dt_s, ctx) -> list[tuple[str, str]]:
        """Retourne la liste des (Pi, origine) survenus pendant ce pas."""
        out = []
        self.incidents_recents = [x for x in self.incidents_recents if x > t - 3 * 86400]
        for pid in self.reg["problemes"]:
            lam = self.taux(pid, ctx)
            if lam > 0 and self.aleas.evenement(pid, lam, dt_s):
                out.append((pid, "spontané"))
        if ctx.get("en_mer", True):
            if self.aleas.evenement("P24_rencontre", self.taux_rencontre_peche(ctx), dt_s):
                out.append(("P24", "rencontre"))
            if self.aleas.evenement("P22_collision", self.taux_collision(ctx), dt_s):
                out.append(("P22", "trafic"))
        restantes = []
        for c in self.cascades:
            if c.t <= t + dt_s:
                if c.condition is None or ctx.get(c.condition, False):
                    out.append((c.pid, c.cause))
            else:
                restantes.append(c)
        self.cascades = restantes
        for pid, _ in out:
            self.occurrences[pid] = self.occurrences.get(pid, 0) + 1
            self.premiere.setdefault(pid, t)
            self.incidents_recents.append(t)
        return out

    def programmer_cascades(self, t, pid):
        for c in self.reg["problemes"][pid].get("cascades", []) or []:
            rng = self.aleas.rng(f"cascade:{pid}->{c['vers']}")
            # la cascade dépend aussi de la protection du problème VISÉ : p_eff = 1 − (1 − p)^m
            m = self.multiplicateur(c["vers"]) if c["vers"] not in ("P8", "P28", "P17") else 1.0
            p_eff = 1.0 - (1.0 - c["prob"]) ** m if c["prob"] < 1.0 else 1.0
            if rng.random() < p_eff:
                lo, hi = c["delai_h"]
                self.cascades.append(Cascade(t + rng.uniform(lo, hi) * 3600.0, c["vers"], f"cascade {pid}",
                                             c.get("condition")))

    def noter(self, pid, t):
        """Enregistre une occurrence d'un problème à effet continu (P9, P12, P15, P27…)."""
        self.occurrences[pid] = self.occurrences.get(pid, 0) + 1
        self.premiere.setdefault(pid, t)

    def tirage(self, nom) -> float:
        return float(self.aleas.rng(nom).random())
