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


_REG_SURCHARGES: dict = {}


def _fusion(base, sur):
    """Copie de `base` où les clés de `sur` remplacent (récursivement pour les dictionnaires)."""
    out = dict(base)
    for k, v in sur.items():
        out[k] = _fusion(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def signature_registre(cfg: dict) -> str:
    import json
    sur = cfg.get("registre_surcharges")
    return json.dumps(sur, sort_keys=True) if sur else ""


def registre_pour(cfg: dict, base: dict) -> dict:
    """Registre à utiliser pour `cfg` : risks.yaml, modifié par `cfg["registre_surcharges"]` s'il existe.

    Permet à une configuration (interface graphique, étude d'effets) de changer un paramètre du
    registre sans toucher à risks.yaml, par exemple {"problemes": {"P2": {"chavirage": {"modele": "hs4"}}}}."""
    sig = signature_registre(cfg)
    if not sig:
        return base
    cle = (id(base), sig)
    if cle not in _REG_SURCHARGES:
        _REG_SURCHARGES[cle] = _fusion(base, cfg["registre_surcharges"])
    return _REG_SURCHARGES[cle]


def _lognormal(rng, med, f90):
    if f90 <= 1.0 or med <= 0:
        return float(med)
    sigma = math.log(f90) / 1.645
    return float(med * math.exp(sigma * rng.normal()))


def facteur_lacet(sigma_deg: float) -> float:
    """Fraction de la vitesse qui reste utile le long de la route quand le cap oscille (écart-type σ) :
    E[cos(écart)] = exp(−σ²/2) pour un écart gaussien [H72]."""
    return math.exp(-0.5 * math.radians(sigma_deg) ** 2)


# ---------------------------------------------------------------------------
# Chavirage (P2) : déferlement des vagues dominantes × taille de la vague devant le bateau  [H71]
# ---------------------------------------------------------------------------
def _p_vague_chavirante(hs, h1, h2):
    """Probabilité qu'une vague chavire le bateau SI elle déferle : rampe linéaire de 0 (H = h1) à 1
    (H = h2), moyennée sur la loi de Rayleigh des hauteurs, P(H > x) = exp(−2 x²/Hs²)."""
    if hs <= 1e-6:
        return 0.0
    c = hs * math.sqrt(math.pi / 8.0)
    r2 = math.sqrt(2.0) / hs
    return c * (math.erf(r2 * h2) - math.erf(r2 * h1)) / (h2 - h1)


def frequence_chavirage(hs, t_moy, exposition, longueur, prm) -> float:
    """Vagues chavirantes par jour, à un coefficient près (calé ensuite sur l'état de référence).

        N = 86400 / Tp                               vagues dominantes par jour (Tp = facteur × T moyenne)
        b = c · (ε − ε0)^n, ε = Hs·k_p/2             fraction de vagues dominantes déferlantes
                                                     (Banner, Babanin & Young 2000), k_p = 4π²/(g·Tp²)
        p = P(la vague est assez haute pour le bateau)   seuils en fraction de la longueur de coque,
                                                     interpolés entre « en travers » et « en bout »

    exposition : |sin| de l'angle entre l'axe du bateau et la direction des vagues (1 = en travers)."""
    if hs <= 0 or t_moy <= 0:
        return 0.0
    tp = prm["facteur_periode_pic"] * t_moy
    eps = hs * (4.0 * math.pi ** 2 / (9.81 * tp * tp)) / 2.0
    if eps <= prm["deferlement_seuil"]:
        return 0.0
    b = min(1.0, prm["deferlement_coef"] * (eps - prm["deferlement_seuil"]) ** prm["deferlement_exposant"])
    (a1, a2), (b1, b2) = prm["seuil_travers_sur_L"], prm["seuil_bout_sur_L"]
    x = min(max(exposition, 0.0), 1.0)
    h1 = longueur * (b1 + (a1 - b1) * x)
    h2 = longueur * (b2 + (a2 - b2) * x)
    return 86400.0 / tp * b * _p_vague_chavirante(hs, h1, h2)


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
        self._k_mois = {m: i for i, m in enumerate(self.mois)}
        self._k_jour = {}
        # origine et tailles en flottants / entiers Python : l'arithmétique sur des scalaires numpy est
        # lente (mêmes valeurs IEEE, donc mêmes indices)
        self._lat0, self._lon0 = float(self.lats[0]), float(self.lons[0])
        self._nla, self._nlo = len(self.lats), len(self.lons)

    def _mois_proche(self, m: str) -> int:
        """Indice du mois GFW à utiliser pour un mois « AAAA-MM » absent des données.

        Même année : comportement d'origine (premier ou dernier mois couvert). Autre année : le même
        mois du calendrier, sinon le mois couvert le plus proche dans le calendrier [H76]."""
        annees = {x[:4] for x in self.mois}
        if m[:4] in annees:
            return 0 if m < self.mois[0] else len(self.mois) - 1
        mm = int(m[5:7])
        return min(range(len(self.mois)), key=lambda i: min((int(self.mois[i][5:7]) - mm) % 12,
                                                            (mm - int(self.mois[i][5:7])) % 12))

    def _idx(self, lat, lon, t_s):
        cle = (lat, lon, t_s)                       # pêche et commerce sont lus au même point, au même instant
        if cle == self.__dict__.get("_der_cle"):
            return self._der_idx
        ix = self._idx_calc(lat, lon, t_s)
        self._der_cle, self._der_idx = cle, ix
        return ix

    def _idx_calc(self, lat, lon, t_s):
        jour = int(t_s // 86400)                    # le mois ne change pas dans une journée UTC : mémorisé par jour
        k = self._k_jour.get(jour)
        if k is None:
            from datetime import datetime, timezone
            m = datetime.fromtimestamp(t_s, timezone.utc).strftime("%Y-%m")
            k = self._k_mois.get(m)
            if k is None:
                k = self._k_mois[m] = self._mois_proche(m)
            self._k_jour[jour] = k
        i = int(round((lat - self._lat0) / self.pas))
        j = int(round((lon - self._lon0) / self.pas))
        if 0 <= i < self._nla and 0 <= j < self._nlo:
            return k, i, j
        return None

    def peche_h_km2(self, lat, lon, t_s):
        ix = self._idx(lat, lon, t_s)
        return float(self.peche[ix]) if ix else 0.0

    def commerce_h_km2(self, lat, lon, t_s):
        ix = self._idx(lat, lon, t_s)
        return float(self.commerce[ix]) if ix else 0.0

    def moyenne_route(self, cfg, distance_km, n=60, route=None):
        """Effort de pêche moyen (annuel) sur les `distance_km` premiers km de l'orthodromie.

        route : {depart, arrivee} pour caler sur une autre route que celle de la mission [H73]."""
        d, a = (route or cfg["mission"])["depart"], (route or cfg["mission"])["arrivee"]
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
        dref = densites.moyenne_route(cfg, dist, route=cal.get("route_reference"))
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

    def __post_init__(self):
        self._mult = {}
        prm = self.reg["problemes"]["P2"].get("chavirage") or {"modele": "hs4"}
        self._chav = prm
        self._chav_L = float(self.cfg["bateau"]["coque"]["L"])
        self._chav_ref = 0.0
        if prm.get("modele", "hs4") == "deferlement":
            self._chav_ref = frequence_chavirage(prm["hs_ref_m"], prm["t_ref_s"], 1.0, self._chav_L, prm)
            if self._chav_ref <= 0:
                raise ValueError("P2.chavirage : l'état de référence (hs_ref_m, t_ref_s) ne déferle pas — "
                                 "le taux ne peut pas être calé dessus")
        self._f_peche = float(self.reg.get("rencontres", {}).get("facteur_rencontre", 1.0))
        self._info_taux = {}
        self._procs = {}
        self._pids_actifs = [pid for pid, P in self.reg["problemes"].items()
                             if self.jeu.taux_base[pid] > 0 and P["modulateur"] not in ("peche", "collision")]

    def etat(self, s):
        return self.cfg["solutions"].get(s, "absente")

    def facteur_chavirage(self, ctx) -> float:
        """Taux de chavirage rapporté à celui de l'état de mer de référence [H71]."""
        hs = ctx["hs"]
        if self._chav.get("modele", "hs4") != "deferlement":
            return (hs / 4.0) ** 4 if hs > 3.0 else 0.0            # ancien modèle [H51]
        return frequence_chavirage(hs, ctx.get("tp", self._chav["t_ref_s"]), ctx.get("exposition", 1.0),
                                   self._chav_L, self._chav) / self._chav_ref

    def proba_redressement(self, drains_bouches: bool) -> float:
        """Probabilité de se redresser après un chavirage : état de S1, drains, stabilité de la coque."""
        P2 = self.reg["problemes"]["P2"]
        p = self.param("P2", "redressement")
        if drains_bouches:
            p = min(p, P2["redressement_drains_bouches"])
        if self._chav.get("avs_redressement", False):
            # AVS < 180° : il existe une position retournée stable ; le redressement n'est plus acquis [H71]
            avs = float(self.cfg["bateau"]["coque"].get("stabilite", {}).get("AVS_deg", 180.0))
            p *= min(1.0, max(0.0, (avs - 90.0) / 90.0))
        return p

    def multiplicateur(self, pid) -> float:
        m = self._mult.get(pid)
        if m is None:
            m = self._mult[pid] = self._multiplicateur(pid)
        return m

    def _multiplicateur(self, pid) -> float:
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
        info = self._info_taux.get(pid)
        if info is None:
            P = self.reg["problemes"][pid]
            info = self._info_taux[pid] = (P["modulateur"], self.jeu.taux_base[pid], P["domaine"] in ("F",))
        mod, base, domaine_f = info
        if base <= 0:
            return 0.0
        hs = ctx["hs"]
        if mod == "aucun":
            f = 1.0
        elif mod == "hs_cube":
            f = (hs / 4.0) ** 3
        elif mod == "chavirage":
            f = self.facteur_chavirage(ctx)
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
        if domaine_f and not ctx["calculateur_actif"]:
            return 0.0
        return base * f * self.multiplicateur(pid)

    def taux_rencontre_peche(self, ctx) -> float:
        m = self.jeu.mult[("P24", "S19", self.etat("S19"))]
        return self.jeu.taux_rencontre_ref * ctx["peche"] / max(self.jeu.densite_ref, 1e-9) * m * self._f_peche

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
        if self.incidents_recents:
            self.incidents_recents = [x for x in self.incidents_recents if x > t - 3 * 86400]
        procs = self._procs
        taux = self.taux
        for pid in self._pids_actifs:               # les problèmes de taux de base nul ne peuvent pas survenir
            lam = taux(pid, ctx)
            if lam > 0:
                pr = procs.get(pid)
                if pr is None:
                    pr = procs[pid] = self.aleas.proc(pid)   # chaque processus a son propre flux de tirages
                if pr.avancer(lam, dt_s):
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
