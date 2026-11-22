"""Environnement réel : météo ERA5, vagues/courants, pêche GFW, trait de côte.

Téléchargement (une fois, reprenable) -> cache data/ -> grilles assemblées ->
interpolation trilinéaire (temps, lat, lon) le long de la trajectoire.

Aucune donnée n'est inventée : si une source échoue, on lève une erreur explicite.
Seul traitement : les cellules marines sans valeur (terre) reçoivent la valeur de
la cellule marine la plus proche (documenté dans HYPOTHESES.md [H03]).
"""
from __future__ import annotations

import asyncio
import gzip
import json
import math
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

from .config import DATA, jeton_gfw

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
VARS_METEO = [
    "temperature_2m", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
    "cloud_cover", "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "precipitation",
]
VARS_MARINE = [
    "wave_height", "wave_direction", "wave_period", "wind_wave_height",
    "swell_wave_height", "swell_wave_direction", "swell_wave_period",
    "ocean_current_velocity", "ocean_current_direction", "sea_surface_temperature",
]
SOURCES = {"meteo": VARS_METEO, "marine": VARS_MARINE}


class QuotaJournalierAtteint(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Grille et période
# ---------------------------------------------------------------------------
def axes_grille(g: dict):
    lats = np.round(np.arange(g["lat"][0], g["lat"][1] + 1e-9, g["pas"]), 3)
    lons = np.round(np.arange(g["lon"][0], g["lon"][1] + 1e-9, g["pas"]), 3)
    return lats, lons


def _meta_path():
    return DATA / "meta.json"


def lire_meta() -> dict:
    p = _meta_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def ecrire_meta(m: dict):
    DATA.mkdir(parents=True, exist_ok=True)
    _meta_path().write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")


def fin_donnees(cfg: dict) -> str:
    """Dernier jour complet disponible en ERA5 (figé dans meta.json au 1er appel)."""
    meta = lire_meta()
    if "fin" in meta:
        return meta["fin"]
    fin = cfg["donnees"]["periode"]["fin"]
    if fin == "auto":
        om = cfg["donnees"]["open_meteo"]
        aujourd = datetime.now(timezone.utc).date()
        r = requests.get(om["archive_url"], params=dict(
            latitude=50, longitude=-30, hourly="wind_speed_10m,shortwave_radiation",
            start_date=str(aujourd - timedelta(days=20)), end_date=str(aujourd),
            models=om["modele_meteo"]), timeout=60)
        r.raise_for_status()
        h = r.json()["hourly"]
        ok = [t for t, a, b in zip(h["time"], h["wind_speed_10m"], h["shortwave_radiation"])
              if a is not None and b is not None]
        dernier = datetime.fromisoformat(ok[-1])
        # dernier jour *complet* (jusqu'à 23:00)
        jour = dernier.date() if dernier.hour == 23 else dernier.date() - timedelta(days=1)
        fin = str(jour)
    meta["fin"] = fin
    ecrire_meta(meta)
    return fin


def annee_de_base(cfg: dict) -> int:
    return int(cfg["donnees"]["periode"]["debut"][:4])


def periode_annee(cfg: dict, annee: int | None = None) -> tuple[str, str]:
    """(début, fin) des données d'une année. L'année de base suit `donnees.periode` ; une autre année
    couvre le 1er janvier – 31 décembre (elle doit être passée : ERA5 complet)."""
    base = annee_de_base(cfg)
    if annee is None or int(annee) == base:
        return cfg["donnees"]["periode"]["debut"], fin_donnees(cfg)
    if int(annee) > base:
        raise ValueError(f"Année {annee} postérieure à l'année de base {base} : données incomplètes")
    return f"{int(annee)}-01-01", f"{int(annee)}-12-31"


def nom_grille(grille: dict, annee: int | None = None, cfg: dict | None = None) -> str:
    """grille_2deg.npz pour l'année de base, grille_2deg_2024.npz pour une autre année."""
    suff = "" if annee is None or cfg is None or int(annee) == annee_de_base(cfg) else f"_{int(annee)}"
    return f"grille_{grille['pas']:g}deg{suff}.npz"


def chemin_grille(cfg: dict, annee: int | None = None, strict: bool = True):
    """Grille à utiliser pour simuler : `simulation.grille` = auto (la plus fine disponible), 1deg ou 2deg.

    Pour une année autre que l'année de base, seule la grille principale (2°) est téléchargée."""
    choix = str(cfg.get("simulation", {}).get("grille", "auto"))
    d = cfg["donnees"]
    if annee is not None and int(annee) != annee_de_base(cfg):
        cand = [d["grille"]]
    elif choix == "auto":
        cand = [d["grille_fine"], d["grille"]]
    else:
        cand = [g for g in (d["grille_fine"], d["grille"]) if f"{g['pas']:g}deg" == choix]
        if not cand:
            raise ValueError(f"simulation.grille = {choix!r} : attendu auto, "
                             f"{d['grille_fine']['pas']:g}deg ou {d['grille']['pas']:g}deg")
    for g in cand:
        f = DATA / nom_grille(g, annee, cfg)
        if f.exists():
            return f
    if strict:
        raise FileNotFoundError(f"Aucune grille de données ({', '.join(nom_grille(g, annee, cfg) for g in cand)}) : "
                                "lancer « python main.py donnees ».")
    return None


def mois_complets(cfg: dict, grille: dict, periode: tuple[str, str]) -> list[str]:
    """Mois consécutifs, depuis le début de la période, entièrement présents dans le cache."""
    lats, lons = axes_grille(grille)
    out = []
    for mois, _, _ in tranches_mensuelles(*periode):
        if all(_chemin_point(src, mois, la, lo).exists() for src in SOURCES for la in lats for lo in lons):
            out.append(mois)
        else:
            break
    return out


def telecharger_annees(cfg: dict, log=print) -> dict:
    """Télécharge la grille principale pour les années de `donnees.annees` autres que l'année de base.

    Ordre : mois par mois, toutes années confondues (janvier 2024, janvier 2025, février 2024…), pour
    qu'un téléchargement interrompu par le quota laisse le MÊME début d'année exploitable partout.
    Reprise automatique : les fichiers déjà en cache ne sont pas redemandés. Lève QuotaJournalierAtteint."""
    base = annee_de_base(cfg)
    annees = [int(a) for a in cfg["donnees"].get("annees", []) if int(a) != base]
    g = cfg["donnees"]["grille"]
    fait = 0
    for m in range(1, 13):
        for a in annees:
            d0 = datetime(a, m, 1).date()
            d1 = (d0 + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            fait += telecharger_open_meteo(cfg, g, log=log, periode=(str(d0), str(d1)))
    return {"annees": annees, "points": fait}


def assembler_annees(cfg: dict, log=print) -> dict:
    """Assemble, pour chaque année supplémentaire, les mois complets en cache. {année: [mois]}."""
    base = annee_de_base(cfg)
    g = cfg["donnees"]["grille"]
    out = {}
    for a in cfg["donnees"].get("annees", []):
        a = int(a)
        if a == base:
            continue
        per = periode_annee(cfg, a)
        mois = mois_complets(cfg, g, per)
        out[a] = mois
        if not mois:
            continue
        f = DATA / nom_grille(g, a, cfg)
        deja = lire_meta().get("assemblages", {}).get(f.name, {}).get("mois")
        if f.exists() and deja == mois:
            continue
        assembler(cfg, g, suffixe=f"_{a}", periode=per, mois_liste=mois)
        log(f"Grille {a} assemblée : {mois[0]} à {mois[-1]}")
    return out


def tranches_mensuelles(debut: str, fin: str):
    d = datetime.fromisoformat(debut).date()
    f = datetime.fromisoformat(fin).date()
    while d <= f:
        prochain = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
        yield d.strftime("%Y-%m"), d, min(f, prochain - timedelta(days=1))
        d = prochain


# ---------------------------------------------------------------------------
# Open-Meteo : téléchargement reprenable avec limitation de débit
# ---------------------------------------------------------------------------
class Limiteur:
    """Poids Open-Meteo = n_points * max(1, nvars/10) * max(1, jours/14)."""

    def __init__(self, par_minute: float, par_heure: float):
        self.pm, self.ph = par_minute, par_heure
        self.hist: deque[tuple[float, float]] = deque()

    def attendre(self, poids: float):
        while True:
            now = time.time()
            while self.hist and now - self.hist[0][0] > 3600:
                self.hist.popleft()
            h = sum(w for _, w in self.hist)
            m = sum(w for t, w in self.hist if now - t < 60)
            if h + poids <= self.ph and m + poids <= self.pm:
                self.hist.append((now, poids))
                return
            attente = 5 if m + poids > self.pm else 30
            time.sleep(attente)


def poids_requete(n_points, n_vars, jours):
    return n_points * max(1.0, n_vars / 10) * max(1.0, jours / 14)


def _chemin_point(src, mois, lat, lon) -> Path:
    return DATA / "raw" / src / mois / f"{lat:+07.2f}_{lon:+08.2f}.npz"


def _requete(url, params, essais=6):
    for k in range(essais):
        try:
            r = requests.get(url, params=params, timeout=180)
        except requests.RequestException as e:
            time.sleep(10 * (k + 1))
            last = e
            continue
        if r.status_code == 429:
            raison = r.text
            if "Daily" in raison or "daily" in raison:
                raise QuotaJournalierAtteint(raison)
            time.sleep(65)
            continue
        if r.status_code >= 500:
            time.sleep(15 * (k + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Open-Meteo HTTP {r.status_code}: {r.text[:300]}")
        return r.json()
    raise RuntimeError(f"Open-Meteo injoignable après {essais} essais ({params.get('start_date')})")


def _convertir(src, var, valeurs, unite):
    a = np.array([np.nan if v is None else v for v in valeurs], dtype=np.float32)
    if unite == "km/h":
        a /= 3.6
    return a


def telecharger_open_meteo(cfg: dict, grille: dict, log=print, periode: tuple[str, str] | None = None):
    om = cfg["donnees"]["open_meteo"]
    debut, fin = periode or periode_annee(cfg)
    lats, lons = axes_grille(grille)
    points = [(la, lo) for la in lats for lo in lons]
    lim = Limiteur(om["poids_max_par_minute"], om["poids_max_par_heure"])
    n = om["points_par_requete"]
    total_fait = 0
    for mois, d0, d1 in tranches_mensuelles(debut, fin):
        jours = (d1 - d0).days + 1
        for src, vars_ in SOURCES.items():
            manquants = [p for p in points if not _chemin_point(src, mois, *p).exists()]
            if not manquants:
                continue
            log(f"[{src} {mois}] {len(manquants)} points à télécharger")
            for i in range(0, len(manquants), n):
                lot = manquants[i:i + n]
                params = dict(
                    latitude=",".join(f"{p[0]:.2f}" for p in lot),
                    longitude=",".join(f"{p[1]:.2f}" for p in lot),
                    hourly=",".join(vars_), start_date=str(d0), end_date=str(d1),
                    timezone="GMT",
                )
                if src == "meteo":
                    url = om["archive_url"]
                    params.update(models=om["modele_meteo"], wind_speed_unit="ms")
                else:
                    url = om["marine_url"]
                    params.update(cell_selection="sea")
                lim.attendre(poids_requete(len(lot), len(vars_), jours))
                rep = _requete(url, params)
                if isinstance(rep, dict):
                    rep = [rep]
                if len(rep) != len(lot):
                    raise RuntimeError("Réponse Open-Meteo : nombre de points inattendu")
                for (la, lo), r in zip(lot, rep):
                    h, u = r["hourly"], r.get("hourly_units", {})
                    t = np.array([datetime.fromisoformat(x).replace(tzinfo=timezone.utc).timestamp()
                                  for x in h["time"]], dtype=np.int64)
                    arrs = {v: _convertir(src, v, h[v], u.get(v, "")) for v in vars_}
                    p = _chemin_point(src, mois, la, lo)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(p, t=t, lat_reel=r.get("latitude", la),
                                        lon_reel=r.get("longitude", lo), **arrs)
                total_fait += len(lot)
            log(f"[{src} {mois}] ok")
    return total_fait


def etat_cache(cfg: dict, grille: dict, periode: tuple[str, str] | None = None) -> dict:
    debut, fin = periode or periode_annee(cfg)
    lats, lons = axes_grille(grille)
    res = {}
    for mois, _, _ in tranches_mensuelles(debut, fin):
        for src in SOURCES:
            n = sum(_chemin_point(src, mois, la, lo).exists() for la in lats for lo in lons)
            res[f"{src} {mois}"] = (n, len(lats) * len(lons))
    return res


def instantane(cfg: dict, grille: dict, quand: datetime, src: str, vars_: list[str]):
    """Champ brut à une heure donnée, lu directement dans le cache (sans assemblage)."""
    lats, lons = axes_grille(grille)
    mois = quand.strftime("%Y-%m")
    ts = int(quand.replace(tzinfo=timezone.utc).timestamp())
    res = {v: np.full((len(lats), len(lons)), np.nan, dtype=np.float32) for v in vars_}
    for i, la in enumerate(lats):
        for j, lo in enumerate(lons):
            p = _chemin_point(src, mois, la, lo)
            if not p.exists():
                raise FileNotFoundError(p)
            z = np.load(p)
            k = int(np.searchsorted(z["t"], ts))
            for v in vars_:
                res[v][i, j] = z[v][k]
    return lats, lons, res


def serie_point(cfg: dict, grille: dict, lat: float, lon: float, mois: str, src: str, vars_: list[str]):
    lats, lons = axes_grille(grille)
    la = lats[np.argmin(abs(lats - lat))]
    lo = lons[np.argmin(abs(lons - lon))]
    z = np.load(_chemin_point(src, mois, la, lo))
    return (la, lo), z["t"], {v: z[v] for v in vars_}


# ---------------------------------------------------------------------------
# Assemblage en grilles
# ---------------------------------------------------------------------------
def _uv_depuis(vitesse, direction_deg, provenance: bool):
    """Composantes (est, nord) du vecteur 'vers'. provenance=True : convention météo (d'où vient)."""
    d = np.radians(direction_deg)
    s = -1.0 if provenance else 1.0
    return s * vitesse * np.sin(d), s * vitesse * np.cos(d)


def _remplir_plus_proche(a: np.ndarray, lats, lons):
    """a[t, i, j] : remplit les NaN par la cellule valide la plus proche (distance sur la sphère)."""
    valide = ~np.isnan(a)
    if valide.all():
        return a, 0
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    pts = np.c_[LA.ravel(), LO.ravel()]
    nt = a.shape[0]
    flat = a.reshape(nt, -1)
    n_rempli = 0
    # masque statique : cellule valide au moins une fois
    toujours_nan = np.isnan(flat).all(axis=0)
    src_idx = np.where(~toujours_nan)[0]
    if len(src_idx) == 0:
        raise RuntimeError("Aucune cellule marine valide")
    from .geo import haversine
    for k in np.where(toujours_nan)[0]:
        d = haversine(pts[k, 0], pts[k, 1], pts[src_idx, 0], pts[src_idx, 1])
        flat[:, k] = flat[:, src_idx[np.argmin(d)]]
        n_rempli += 1
    # trous temporels résiduels : remplissage avant/arrière
    for k in np.where(np.isnan(flat).any(axis=0))[0]:
        col = flat[:, k]
        ok = ~np.isnan(col)
        if ok.any():
            flat[:, k] = np.interp(np.arange(nt), np.where(ok)[0], col[ok])
    return flat.reshape(a.shape), n_rempli


def assembler(cfg: dict, grille: dict, mois_max: str | None = None, suffixe: str = "",
              periode: tuple[str, str] | None = None, mois_liste: list[str] | None = None) -> Path:
    debut, fin = periode or periode_annee(cfg)
    lats, lons = axes_grille(grille)
    if mois_liste is None:
        mois_liste = [m for m, _, _ in tranches_mensuelles(debut, fin) if mois_max is None or m <= mois_max]
    out = {}
    t_ref = None
    infos = {}
    for src, vars_ in SOURCES.items():
        blocs = {v: [] for v in vars_}
        temps = []
        for mois in mois_liste:
            t_m = None
            tranche = {v: [] for v in vars_}
            for la in lats:
                for v in vars_:
                    tranche[v].append([])
                for lo in lons:
                    p = _chemin_point(src, mois, la, lo)
                    if not p.exists():
                        raise FileNotFoundError(f"Cache incomplet : {p} (lancer 'python main.py donnees')")
                    z = np.load(p)
                    t_m = z["t"] if t_m is None else t_m
                    for v in vars_:
                        tranche[v][-1].append(z[v])
            for v in vars_:
                blocs[v].append(np.transpose(np.array(tranche[v], dtype=np.float32), (2, 0, 1)))
            temps.append(t_m)
        t = np.concatenate(temps)
        t_ref = t if t_ref is None else t_ref
        if not np.array_equal(t, t_ref):
            raise RuntimeError("Axes temporels météo/marine différents")
        for v in vars_:
            out[f"{src}/{v}"] = np.concatenate(blocs[v], axis=0)
    # remplissage des cellules marines terrestres
    for v in VARS_MARINE:
        out[f"marine/{v}"], n = _remplir_plus_proche(out[f"marine/{v}"], lats, lons)
        infos[v] = n
    # vecteurs
    ue, vn = _uv_depuis(out["meteo/wind_speed_10m"], out["meteo/wind_direction_10m"], True)
    out["vent_u"], out["vent_v"] = ue, vn
    cu, cv = _uv_depuis(out["marine/ocean_current_velocity"], out["marine/ocean_current_direction"], False)
    out["courant_u"], out["courant_v"] = cu, cv
    wu, wv = _uv_depuis(np.ones_like(out["marine/wave_direction"]), out["marine/wave_direction"], True)
    out["vague_dir_u"], out["vague_dir_v"] = wu, wv  # direction de propagation (unitaire)
    import os
    nom = DATA / f"grille_{grille['pas']:g}deg{suffixe}.npz"
    tmp = nom.with_name(nom.stem + f".tmp{os.getpid()}.npz")
    np.savez_compressed(tmp, t=t_ref, lats=lats, lons=lons,
                        **{k.replace("/", "__"): a.astype(np.float32) for k, a in out.items()})
    os.replace(tmp, nom)                     # écriture atomique
    meta = lire_meta()
    meta.setdefault("assemblages", {})[nom.name] = dict(
        mois=mois_liste, n_t=int(len(t_ref)), lats=[float(lats[0]), float(lats[-1])],
        lons=[float(lons[0]), float(lons[-1])], cellules_marines_remplies=infos,
        date=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    ecrire_meta(meta)
    return nom


# ---------------------------------------------------------------------------
# Interpolation le long de la trajectoire
# ---------------------------------------------------------------------------
class Environnement:
    """Échantillonnage trilinéaire (t, lat, lon) des champs réels en cache.

    Les champs sont empilés dans un tableau [t, lat, lon, champ] mappé en mémoire
    (data/pile_*.npy) : une interpolation = 8 lectures vectorielles, et les processus
    du Monte-Carlo partagent les mêmes pages mémoire.
    Les rayonnements ERA5 d'Open-Meteo sont des moyennes sur l'heure *précédente* :
    ils sont lus à t + 30 min [H22].
    """

    CHAMPS = {
        "t_air": "meteo__temperature_2m", "rafales": "meteo__wind_gusts_10m",
        "nuages": "meteo__cloud_cover", "ghi": "meteo__shortwave_radiation",
        "dni_h": "meteo__direct_radiation", "dhi": "meteo__diffuse_radiation",
        "pluie": "meteo__precipitation", "vent_u": "vent_u", "vent_v": "vent_v",
        "hs": "marine__wave_height", "tp": "marine__wave_period",
        "hs_houle": "marine__swell_wave_height", "hs_mer_vent": "marine__wind_wave_height",
        "vague_dir_u": "vague_dir_u", "vague_dir_v": "vague_dir_v",
        "courant_u": "courant_u", "courant_v": "courant_v",
        "sst": "marine__sea_surface_temperature",
    }
    RAYONNEMENT = ("ghi", "dni_h", "dhi")

    def __init__(self, chemin: Path | str | None = None):
        if chemin is None:
            fine = DATA / "grille_1deg.npz"
            chemin = fine if fine.exists() else DATA / "grille_2deg.npz"
        self.chemin = Path(chemin)
        self.noms = list(self.CHAMPS)
        self.idx = {k: i for i, k in enumerate(self.noms)}
        pile = self.chemin.with_name("pile_" + self.chemin.stem + ".npy")
        axes = self.chemin.with_name("axes_" + self.chemin.stem + ".npz")
        if not pile.exists() or not axes.exists() or pile.stat().st_mtime < self.chemin.stat().st_mtime:
            import os
            z = np.load(self.chemin)
            tmp_a = axes.with_name(axes.stem + f".tmp{os.getpid()}.npz")
            np.savez(tmp_a, t=z["t"], lats=z["lats"], lons=z["lons"])
            P = np.stack([z[self.CHAMPS[k]] for k in self.noms], axis=-1).astype(np.float32)
            tmp_p = pile.with_name(pile.stem + f".tmp{os.getpid()}.npy")
            np.save(tmp_p, P)
            del P
            os.replace(tmp_p, pile)          # écriture atomique (plusieurs processus possibles)
            os.replace(tmp_a, axes)
        ax = np.load(axes)
        self.t = ax["t"].astype(np.float64)
        self.lats = ax["lats"].astype(np.float64)
        self.lons = ax["lons"].astype(np.float64)
        self.P = np.load(pile, mmap_mode="r")
        # Vue ndarray du même fichier mappé (aucune copie) : l'indexation d'un np.memmap crée un objet
        # memmap à chaque lecture, ce qui coûte plus cher que la lecture elle-même.
        self._A = np.asarray(self.P)
        self._nt, self._nla, self._nlo = len(self.t), len(self.lats), len(self.lons)
        self._nc = len(self.noms)
        self._w = np.empty((1, 8))
        self.t_debut, self.t_fin = self.t[0], self.t[-1]
        self._dt = self.t[1] - self.t[0]
        self._dla = self.lats[1] - self.lats[0]
        self._dlo = self.lons[1] - self.lons[0]
        self._irad = np.array([self.idx[k] for k in self.RAYONNEMENT])
        # Copies en flottants Python des origines et des pas (l'arithmétique sur des scalaires numpy est
        # plusieurs fois plus lente ; mêmes valeurs IEEE, donc mêmes résultats)
        self._t0f, self._la0f, self._lo0f = float(self.t[0]), float(self.lats[0]), float(self.lons[0])
        self._dtf, self._dlaf, self._dlof = float(self._dt), float(self._dla), float(self._dlo)
        r = [int(i) for i in self._irad]
        self._rad = slice(r[0], r[-1] + 1) if r == list(range(r[0], r[-1] + 1)) else self._irad
        self._cle_B = self._cle_B2 = None
        self._B = self._B2 = None

    def hors_domaine(self, lat, lon) -> bool:
        return not (self.lats[0] <= lat <= self.lats[-1] and self.lons[0] <= lon <= self.lons[-1])

    def _coins(self, x, x0, dx, n):
        f = (min(max(x, x0), x0 + dx * (n - 1)) - x0) / dx
        i = min(int(f), n - 2)
        return i, f - i

    def vecteur(self, t_s: float, lat: float, lon: float) -> np.ndarray:
        """Tous les champs à (t, lat, lon), ordre self.noms (scalaire, rapide)."""
        A = self._A
        coins = self._coins
        it, ft = coins(t_s, self._t0f, self._dtf, self._nt)
        ia, fa = coins(lat, self._la0f, self._dlaf, self._nla)
        io, fo = coins(lon, self._lo0f, self._dlof, self._nlo)
        # Poids des 8 coins, dans l'ordre (t, lat, lon), et produit matriciel (1×8)·(8×champs) : ce sont
        # exactement les opérations que faisait np.tensordot (mêmes produits, même appel BLAS), sans
        # ses vérifications ni ses tableaux intermédiaires.
        nc = self._nc
        a0, a1, o0, o1 = 1 - fa, fa, 1 - fo, fo
        t0, t1 = 1 - ft, ft
        w = self._w
        w[0, 0] = t0 * a0 * o0; w[0, 1] = t0 * a0 * o1; w[0, 2] = t0 * a1 * o0; w[0, 3] = t0 * a1 * o1  # noqa: E702
        w[0, 4] = t1 * a0 * o0; w[0, 5] = t1 * a0 * o1; w[0, 6] = t1 * a1 * o0; w[0, 7] = t1 * a1 * o1  # noqa: E702
        # bloc des 8 coins : réutilisé tant que la cellule (t, lat, lon) ne change pas (mêmes valeurs)
        cle = (it, ia, io)
        if cle == self._cle_B:
            B = self._B
        else:
            B = self._B = A[it:it + 2, ia:ia + 2, io:io + 2, :].reshape(8, nc).astype(np.float64)
            self._cle_B = cle
        v = np.dot(w, B).reshape(nc)
        # rayonnement : moyenne de l'heure précédente -> lu à t + 30 min
        it2, ft2 = coins(t_s + 1800.0, self._t0f, self._dtf, self._nt)
        if it2 != it or ft2 != ft:
            t0, t1 = 1 - ft2, ft2
            w[0, 0] = t0 * a0 * o0; w[0, 1] = t0 * a0 * o1; w[0, 2] = t0 * a1 * o0; w[0, 3] = t0 * a1 * o1  # noqa: E702
            w[0, 4] = t1 * a0 * o0; w[0, 5] = t1 * a0 * o1; w[0, 6] = t1 * a1 * o0; w[0, 7] = t1 * a1 * o1  # noqa: E702
            rad = self._rad
            # ordre Fortran : c'est la disposition que produisait l'indexation par liste d'indices, et le
            # noyau BLAS (donc l'arrondi) dépend de la disposition mémoire
            cle2 = (it2, ia, io)
            if cle2 == self._cle_B2:
                B2 = self._B2
            else:
                B2 = self._B2 = A[it2:it2 + 2, ia:ia + 2, io:io + 2, rad].reshape(8, -1).astype(np.float64, order="F")
                self._cle_B2 = cle2
            v[rad] = np.dot(w, B2).reshape(-1)
        return v

    def echantillon(self, t_s, lat, lon, champs=None) -> dict:
        """Version dictionnaire (scalaires)."""
        v = self.vecteur(float(t_s), float(lat), float(lon))
        res = {k: v[self.idx[k]] for k in (champs or self.noms)}
        if "vent_u" in res and "vent_v" in res:
            res["vent"] = float(np.hypot(res["vent_u"], res["vent_v"]))
        if "courant_u" in res and "courant_v" in res:
            res["courant"] = float(np.hypot(res["courant_u"], res["courant_v"]))
        return res


# ---------------------------------------------------------------------------
# Global Fishing Watch (4Wings)
# ---------------------------------------------------------------------------
def _agreger_gfw(df, lats_c, lons_c, pas):
    H = np.zeros((len(lats_c), len(lons_c)), dtype=np.float64)
    if df is None or len(df) == 0:
        return H
    i = np.floor((df["lat"].to_numpy(float) - lats_c[0] + pas / 2) / pas).astype(int)
    j = np.floor((df["lon"].to_numpy(float) - lons_c[0] + pas / 2) / pas).astype(int)
    ok = (i >= 0) & (i < len(lats_c)) & (j >= 0) & (j < len(lons_c))
    np.add.at(H, (i[ok], j[ok]), df["hours"].to_numpy(float)[ok])
    return H


def telecharger_gfw(cfg: dict, log=print) -> dict:
    import gfwapiclient as gfw

    g = cfg["donnees"]["gfw"]
    jeton = jeton_gfw(cfg)
    if not jeton:
        raise RuntimeError("Jeton GFW absent (secrets.yaml ou GFW_API_ACCESS_TOKEN)")
    pas = g["resolution_agregation"]
    lats_c = np.arange(g["bbox"]["lat"][0] + pas / 2, g["bbox"]["lat"][1], pas)
    lons_c = np.arange(g["bbox"]["lon"][0] + pas / 2, g["bbox"]["lon"][1], pas)
    # découpage en tuiles de 10° x 10° pour limiter la taille des rapports
    tuiles = []
    for la in range(int(g["bbox"]["lat"][0]), int(g["bbox"]["lat"][1]), 10):
        for lo in range(int(g["bbox"]["lon"][0]), int(g["bbox"]["lon"][1]), 10):
            la1, lo1 = min(la + 10, g["bbox"]["lat"][1]), min(lo + 10, g["bbox"]["lon"][1])
            tuiles.append({"type": "Polygon", "coordinates": [[[lo, la], [lo1, la], [lo1, la1], [lo, la1], [lo, la]]]})
    rep = DATA / "gfw"
    rep.mkdir(parents=True, exist_ok=True)

    async def un_mois(client, mois, quoi):
        f = rep / f"{quoi}_{mois}.npy"
        if f.exists():
            return np.load(f)
        d0 = datetime.strptime(mois, "%Y-%m").date()
        d1 = (d0 + timedelta(days=32)).replace(day=1)
        H = np.zeros((len(lats_c), len(lons_c)))
        for geo in tuiles:
            for essai in range(4):
                try:
                    if quoi == "peche":
                        r = await client.fourwings.create_fishing_effort_report(
                            spatial_resolution="LOW", temporal_resolution="MONTHLY",
                            start_date=str(d0), end_date=str(d1), geojson=geo)
                    else:
                        r = await client.fourwings.create_ais_presence_report(
                            spatial_resolution="LOW", temporal_resolution="MONTHLY",
                            filters=["vessel_type in ('cargo','tanker')"],
                            start_date=str(d0), end_date=str(d1), geojson=geo)
                    H += _agreger_gfw(r.df(), lats_c, lons_c, pas)
                    break
                except Exception as e:  # noqa: BLE001
                    msg = str(e)
                    if "no data" in msg.lower() or "empty" in msg.lower():
                        break
                    if essai == 3:
                        raise RuntimeError(f"GFW {quoi} {mois} : {msg[:300]}") from e
                    await asyncio.sleep(10 * (essai + 1))
        np.save(f, H)
        log(f"[gfw {quoi} {mois}] {H.sum():.0f} h")
        return H

    async def tout():
        client = gfw.Client(access_token=jeton)
        res = {}
        for quoi in ("peche", "commerce"):
            res[quoi] = np.stack([await un_mois(client, m, quoi) for m in g["mois"]])
        return res

    res = asyncio.run(tout())
    # heures / km² / mois : surface de cellule
    surf = (np.radians(pas) * 6371.0) ** 2 * np.cos(np.radians(lats_c))[:, None]
    np.savez_compressed(DATA / "gfw.npz", mois=np.array(g["mois"]), lats=lats_c, lons=lons_c,
                        peche_h=res["peche"], commerce_h=res["commerce"],
                        peche_h_km2=res["peche"] / surf, commerce_h_km2=res["commerce"] / surf)
    return res


# ---------------------------------------------------------------------------
# Trait de côte (Natural Earth 10 m)
# ---------------------------------------------------------------------------
def telecharger_cote(cfg: dict, log=print) -> Path:
    from shapely import wkb
    from shapely.geometry import box, shape
    from shapely.ops import unary_union

    c = cfg["donnees"]["cote"]
    f = DATA / "cote.wkb"
    if f.exists():
        return f
    cadre = box(c["bbox"]["lon"][0], c["bbox"]["lat"][0], c["bbox"]["lon"][1], c["bbox"]["lat"][1])
    geoms = []
    for url in c["sources"]:
        log(f"[côte] {url.rsplit('/', 1)[-1]}")
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        for feat in r.json()["features"]:
            g = shape(feat["geometry"])
            if g.intersects(cadre):
                geoms.append(g.intersection(cadre))
    terre = unary_union(geoms)
    f.write_bytes(wkb.dumps(terre))
    log(f"[côte] {len(geoms)} polygones conservés")
    return f


def charger_cote():
    from shapely import wkb
    from shapely.prepared import prep
    g = wkb.loads((DATA / "cote.wkb").read_bytes())
    return g, prep(g)


class MasqueCote:
    """Grille « y a-t-il de la terre à moins d'une maille ? » pour éviter le test géométrique au large.

    Une maille (0,25°) est marquée si la terre touche la maille élargie d'une maille de chaque côté. Si les
    deux extrémités d'un déplacement sont dans des mailles non marquées et que le déplacement fait moins
    d'une maille, le segment ne peut pas toucher la terre : le résultat est exactement celui du test
    shapely, qui n'est alors pas appelé (au large, c'est-à-dire presque toujours)."""

    PAS = 0.25

    def __init__(self, terre, terre_prep, fichier: Path | None = None):
        from shapely.geometry import box
        x0, y0, x1, y1 = terre.bounds
        self.lon0, self.lat0 = math.floor(x0) - 1.0, math.floor(y0) - 1.0
        nlo = int(math.ceil((x1 + 1.0 - self.lon0) / self.PAS))
        nla = int(math.ceil((y1 + 1.0 - self.lat0) / self.PAS))
        cle = f"{terre.bounds}|{terre.area:.6f}|{self.PAS}"
        if fichier is not None and fichier.exists():
            z = np.load(fichier, allow_pickle=False)
            if str(z["cle"]) == cle:
                self.proche = z["proche"]
                self.nla, self.nlo = self.proche.shape
                return
        p = self.PAS
        proche = np.zeros((nla, nlo), dtype=bool)
        for i in range(nla):
            la = self.lat0 + i * p
            for j in range(nlo):
                lo = self.lon0 + j * p
                proche[i, j] = terre_prep.intersects(box(lo - p, la - p, lo + 2 * p, la + 2 * p))
        self.proche = proche
        self.nla, self.nlo = nla, nlo
        if fichier is not None:
            import os
            tmp = fichier.with_name(fichier.stem + f".tmp{os.getpid()}.npz")
            np.savez_compressed(tmp, proche=proche, cle=np.array(cle))
            os.replace(tmp, fichier)

    def au_large(self, lat1, lon1, lat2, lon2) -> bool:
        """Vrai si le segment ne peut pas toucher la terre (sinon : faire le test exact)."""
        p = self.PAS
        if abs(lat2 - lat1) >= p or abs(lon2 - lon1) >= p:
            return False
        i1, j1 = int((lat1 - self.lat0) // p), int((lon1 - self.lon0) // p)
        i2, j2 = int((lat2 - self.lat0) // p), int((lon2 - self.lon0) // p)
        if not (0 <= i1 < self.nla and 0 <= i2 < self.nla and 0 <= j1 < self.nlo and 0 <= j2 < self.nlo):
            # hors de l'emprise du trait de côte (élargie d'un degré) : aucune terre connue ici
            return (i1 < 0 or i1 >= self.nla or j1 < 0 or j1 >= self.nlo) and \
                   (i2 < 0 or i2 >= self.nla or j2 < 0 or j2 >= self.nlo)
        return not (self.proche[i1, j1] or self.proche[i2, j2])


_MASQUES: dict = {}


def masque_cote(cote) -> MasqueCote:
    """Masque associé à un trait de côte chargé (mis en cache par processus et sur disque)."""
    m = _MASQUES.get(id(cote[0]))
    if m is None:
        m = _MASQUES[id(cote[0])] = MasqueCote(cote[0], cote[1], DATA / "cote_masque.npz")
    return m
