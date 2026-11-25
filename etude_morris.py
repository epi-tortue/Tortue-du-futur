#!/usr/bin/env python3
"""Étude de sensibilité (méthode de Morris) : qu'est-ce qui est le plus critique dans la conception ?

Script autonome : il importe `sim/` mais ne modifie aucun fichier du projet (ni config.yaml, ni risks.yaml).
Les sorties vont dans out/morris/<etiquette>/ ; TOUT est enregistré :
  configs.json.gz       config de base, grille météo, commit git, facteurs, niveaux et config complète de chaque cas
                        (écrit avant de simuler)
  checkpoint.sqlite3    résultats enregistrés après chaque mission, reprise automatique après interruption
  runs_pannes.json.gz   chaque run complet : graine, jeu, fin, cause, trace, occurrences P1–P28, 1re apparition…
  runs_pannes.csv       une ligne par run : niveau de chaque facteur + résultats + occ_Pi / j1_Pi (tableur, pandas)
  runs_physique.*       idem pour la passe physique (fin, jours, distance, toutes les stats de la mission)
                        (chaque passe est écrite dès qu'elle finit : rien n'est perdu si la suivante plante)
  brut.json             plan de Morris + indicateurs moyens par config (sert à --analyser)
  <passe>__<date>.csv   mu*, mu, sigma, IC 90 % de chaque facteur pour chaque indicateur
  *.png, rapport.md     figures et rapport

Ce qui varie (« facteurs »), chacun sur 3 niveaux : bas / nominal / haut
  - paramètres physiques, autour des valeurs de config.yaml (±20 % par défaut, voir PHYSIQUES) ;
    la géométrie de la coque Testa (L, S, T, Cb, stabilité) n'est PAS touchée ;
  - état des solutions S1–S20 : absente / partielle / validee.

Deux passes, sur la même météo (même année, même date de largage pour toutes les configs) :
  - « physique » : bateau + énergie seuls, GPS parfait, sans pannes ni risques. Déterministe à météo donnée :
    1 run par config ;
  - « pannes »   : simulation complète (estimateur Codac, pannes capteurs, registre P1–P28). N runs par config,
    avec les MÊMES graines pour toutes les configs (nombres aléatoires communs) : la différence entre deux
    configs voisines ne vient que du facteur changé, pas du hasard.

Plan de Morris : r trajectoires ; chacune part d'un point aléatoire de la grille et change les k facteurs
un par un, d'un cran (bas↔nominal ou nominal↔haut), dans un ordre aléatoire. Chaque pas donne un « effet
élémentaire » du facteur changé. Pour chaque facteur et chaque indicateur :
  mu*   = moyenne des |effets|   -> influence (le classement se fait là-dessus)
  mu    = moyenne signée         -> sens : > 0 = monter le facteur augmente l'indicateur
  sigma = écart-type des effets  -> non-linéarité / interactions avec les autres facteurs
Un effet est exprimé « par cran » : différence d'indicateur quand on passe au niveau supérieur.
Intervalle à 90 % de mu* par bootstrap sur les trajectoires.

Tous les indicateurs sont calculés à partir des mêmes runs : les mesurer tous ne coûte aucun run de plus.

Exemples
  python3 etude_morris.py --plan                         # taille du plan, sans rien simuler
  python3 etude_morris.py                                # date de config.yaml, r = 10, 25 runs/config
  python3 etude_morris.py --start 2026-06-15 --r 20
  python3 etude_morris.py --starts 2026-01-01,2026-04-01,2026-06-15   # plusieurs dates + moyenne
  python3 etude_morris.py --facteurs physique --base-solutions validee
  python3 etude_morris.py --analyser out/morris/20260101  # ré-analyse sans relancer

Une étude interrompue reprend automatiquement dans le même dossier de sortie ; utiliser --etiquette
pour démarrer une nouvelle étude avec les mêmes dates et facteurs.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import gzip
import json
import sqlite3
import sys
import time
import warnings
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))

from sim import config as C          # noqa: E402
from sim import montecarlo as MC     # noqa: E402

# ---------------------------------------------------------------------------
# Facteurs physiques : (nom, chemins sous cfg["bateau"], facteur bas, facteur haut, description)
# Le niveau nominal est toujours la valeur de config.yaml (facteur 1). Plages volontairement proches
# du nominal : on cherche ce qui est sensible autour du bateau actuel, pas un autre bateau.
# ---------------------------------------------------------------------------
PHYSIQUES = [
    ("batterie", ["batterie.capacite_wh"], 0.8, 1.2, "capacité batterie"),
    ("panneaux", ["solaire.rendement_cellules"], 0.8, 1.2, "puissance crête solaire (rendement cellules)"),
    ("moteur_pmax", ["propulsion.p_max_w"], 0.8, 1.2, "puissance moteur maximale"),
    ("helice_diam", ["propulsion.diametre_helice_m"], 0.8, 1.2, "diamètre d'hélice"),
    ("helice_rdt", ["propulsion.rendement_helice"], 0.85, 1.15, "rendement d'hélice"),
    ("masse", ["coque.M"], 0.9, 1.1, "déplacement (masse totale)"),
    ("fardage", ["aero.a_front_m2", "aero.a_cote_m2"], 0.8, 1.2, "surfaces au vent (fardage)"),
    ("consommation", ["consommation.calculateur_capteurs_w", "consommation.iridium_moyen_w",
                      "consommation.ais_feu_w", "consommation.divers_w"], 0.8, 1.2, "consommation de bord"),
    ("encrassement", ["biofouling_par_mois"], 0.6, 1.4, "vitesse d'encrassement de la carène"),
]
NIVEAUX_SOLUTION = ["absente", "partielle", "validee"]      # niveau 0 / 0,5 / 1

# indicateurs : (clé, description, sens favorable : +1 plus grand = mieux, -1 plus petit = mieux)
INDICATEURS = {
    "pannes": [
        ("p_arrivee", "P(arrivée)", +1),
        ("p_retrouve", "P(bateau retrouvé)", +1),
        ("p_panne_energie", "P(fin par panne d'énergie)", -1),
        ("reste_nm", "distance restante à la fin (nm)", -1),
        ("jours_fin", "jour de fin de mission", 0),
        ("jours_arrivee", "durée de traversée si arrivée (j)", -1),
        ("blackouts", "nombre de black-outs", -1),
        ("e_moteur", "énergie moteur", 0),
    ],
    "physique": [
        ("arrivee", "arrivée (0/1)", +1),
        ("jours", "jour de fin (arrivée ou fin des données)", -1),
        ("reste_nm", "distance restante à la fin (nm)", -1),
        ("blackouts", "nombre de black-outs", -1),
        ("e_moteur", "énergie moteur", 0),
    ],
}
INDICATEUR_PRINCIPAL = {"pannes": "p_arrivee", "physique": "reste_nm"}


# ---------------------------------------------------------------------------
# Facteurs
# ---------------------------------------------------------------------------
def _get(d, chemin):
    for p in chemin.split("."):
        d = d[p]
    return d


def _set(d, chemin, v):
    parties = chemin.split(".")
    for p in parties[:-1]:
        d = d[p]
    d[parties[-1]] = v


def construire_facteurs(cfg, quels):
    fac = []
    if quels in ("physique", "tous"):
        for nom, chemins, bas, haut, desc in PHYSIQUES:
            nominal = [_get(cfg["bateau"], c) for c in chemins]
            fac.append({"nom": nom, "type": "physique", "chemins": chemins, "nominal": nominal,
                        "bas": bas, "haut": haut, "desc": desc})
    if quels in ("solutions", "tous"):
        for s in cfg["solutions"]:
            fac.append({"nom": s, "type": "solution", "desc": f"état de {s}"})
    return fac


def appliquer(cfg_base, facteurs, x):
    """Config pour le point x de la grille ({0, 0,5, 1}^k)."""
    cfg = copy.deepcopy(cfg_base)
    for f, xi in zip(facteurs, x):
        if f["type"] == "physique":
            niveau = int(round(float(xi) * 2))
            if niveau == 1:            # nominal : valeur de la config au bit près (trajectoire chaotique)
                continue
            mult = f["bas"] if niveau == 0 else f["haut"]
            for c, v0 in zip(f["chemins"], f["nominal"]):
                _set(cfg["bateau"], c, v0 * mult)
        else:
            cfg["solutions"][f["nom"]] = NIVEAUX_SOLUTION[int(round(float(xi) * 2))]
    return cfg


def libelle_niveaux(f):
    if f["type"] == "solution":
        return "absente / partielle / validee"
    nom = ", ".join(f"{v:g}" for v in f["nominal"])
    return f"×{f['bas']:g} / {nom} / ×{f['haut']:g}"


# ---------------------------------------------------------------------------
# Plan de Morris (grille à 3 niveaux, pas d'un cran = 0,5)
# ---------------------------------------------------------------------------
def plan_morris(k, r, graine):
    rng = np.random.default_rng(graine)
    trajs = []
    for _ in range(r):
        x = rng.integers(0, 3, size=k) / 2.0
        points, pas = [tuple(x)], []
        for i in rng.permutation(k):
            if x[i] == 0.0:
                d = 0.5
            elif x[i] == 1.0:
                d = -0.5
            else:
                d = float(rng.choice([-0.5, 0.5]))
            x = x.copy()
            x[i] += d
            points.append(tuple(x))
            pas.append((int(i), d))
        trajs.append({"points": points, "pas": pas})
    return trajs


def points_uniques(trajs):
    u = {}
    for t in trajs:
        for p in t["points"]:
            u.setdefault(p, f"c{len(u):05d}")
    return u


# ---------------------------------------------------------------------------
# Indicateurs par config
# ---------------------------------------------------------------------------
def _moy(v):
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.mean(v)) if v else float("nan")


def indicateurs_pannes(runs):
    arr = [r for r in runs if r["fin"] == "arrivee"]
    return {
        "p_arrivee": _moy([r["fin"] == "arrivee" for r in runs]),
        "p_retrouve": _moy([bool(r["retrouve"]) for r in runs]),
        "p_panne_energie": _moy([r["fin"] == "panne_energie" for r in runs]),
        "reste_nm": _moy([r["dist_restante_nm"] for r in runs]),
        "jours_fin": _moy([r["jours_fin"] for r in runs]),
        "jours_arrivee": _moy([r["jours_fin"] for r in arr]),
        "blackouts": _moy([r["blackouts"] for r in runs]),
        "e_moteur": _moy([r["e_moteur"] for r in runs]),
        "n_runs": len(runs),
        "fins": {c: sum(r["fin"] == c for r in runs) for c in sorted({r["fin"] for r in runs})},
    }


def indicateurs_physique(o):
    s = o.get("stats", {})
    return {"arrivee": float(o["fin"] == "arrivee"), "jours": float(o["jours"]), "reste_nm": float(o["reste_nm"]),
            "blackouts": float(s.get("blackouts", float("nan"))), "e_moteur": float(s.get("e_moteur", float("nan"))),
            "fin": o["fin"]}


# ---------------------------------------------------------------------------
# Analyse de Morris
# ---------------------------------------------------------------------------
def effets_elementaires(trajs, labels, Y, cle, k):
    """Matrice (r, k) des effets par cran montant (NaN si l'indicateur manque)."""
    ee = np.full((len(trajs), k), np.nan)
    for j, t in enumerate(trajs):
        for n, (i, d) in enumerate(t["pas"]):
            y0 = Y[labels[t["points"][n]]].get(cle, np.nan)
            y1 = Y[labels[t["points"][n + 1]]].get(cle, np.nan)
            ee[j, i] = (y1 - y0) * (0.5 / d)          # ramené à « monter d'un cran »
    return ee


def stats_morris(ee, n_boot=2000, graine=0):
    rng = np.random.default_rng(graine)
    r, k = ee.shape
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # indicateur vide (ex. aucune arrivée)
        mu = np.nanmean(ee, axis=0)
        mu_e = np.nanmean(np.abs(ee), axis=0)
        sigma = np.nanstd(ee, axis=0, ddof=1) if r > 1 else np.zeros(k)
        boots = np.array([np.nanmean(np.abs(ee[rng.integers(0, r, r)]), axis=0) for _ in range(n_boot)])
        lo, hi = np.nanpercentile(boots, 5, axis=0), np.nanpercentile(boots, 95, axis=0)
    return {"mu": mu, "mu_etoile": mu_e, "sigma": sigma, "ic_bas": lo, "ic_haut": hi,
            "n": np.sum(np.isfinite(ee), axis=0)}


def analyser(trajs, labels, Y, facteurs, mode):
    out = {}
    for cle, desc, sens in INDICATEURS[mode]:
        st = stats_morris(effets_elementaires(trajs, labels, Y, cle, len(facteurs)))
        lignes = []
        for i, f in enumerate(facteurs):
            lignes.append({"facteur": f["nom"], "type": f["type"], "desc": f["desc"],
                           "mu_etoile": float(st["mu_etoile"][i]), "mu": float(st["mu"][i]),
                           "sigma": float(st["sigma"][i]), "ic90_bas": float(st["ic_bas"][i]),
                           "ic90_haut": float(st["ic_haut"][i]), "n_effets": int(st["n"][i])})
        lignes.sort(key=lambda l: -(l["mu_etoile"] if np.isfinite(l["mu_etoile"]) else -1))
        out[cle] = {"desc": desc, "sens": sens, "classement": lignes}
    return out


# ---------------------------------------------------------------------------
# Sorties
# ---------------------------------------------------------------------------
def _f(v, n=3):
    return "—" if v is None or not np.isfinite(v) else f"{v:.{n}g}"


def ecrire_csv(dossier, nom, analyse):
    with open(dossier / f"{nom}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["indicateur", "rang", "facteur", "type", "mu_etoile", "ic90_bas", "ic90_haut", "mu", "sigma",
                    "sigma_sur_mu_etoile", "n_effets"])
        for cle, a in analyse.items():
            for rg, l in enumerate(a["classement"], 1):
                ratio = l["sigma"] / l["mu_etoile"] if l["mu_etoile"] else float("nan")
                w.writerow([cle, rg, l["facteur"], l["type"], l["mu_etoile"], l["ic90_bas"], l["ic90_haut"],
                            l["mu"], l["sigma"], ratio, l["n_effets"]])


def figure(dossier, nom, analyse, cle, titre):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    cl = [l for l in analyse[cle]["classement"] if np.isfinite(l["mu_etoile"])]
    if not cl:
        return None
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, max(5, 0.28 * len(cl) + 1.5)))
    noms = [l["facteur"] for l in cl][::-1]
    me = np.array([l["mu_etoile"] for l in cl][::-1])
    lo = np.array([l["ic90_bas"] for l in cl][::-1])
    hi = np.array([l["ic90_haut"] for l in cl][::-1])
    coul = ["#3b6ea5" if l["type"] == "physique" else "#c4793a" for l in cl][::-1]
    a1.barh(noms, me, color=coul, xerr=[me - lo, hi - me], ecolor="#555", capsize=2)
    a1.set_xlabel(f"mu* : |effet| moyen d'un cran sur « {analyse[cle]['desc']} »")
    a1.set_title("Classement (bleu : physique, orange : solution)")
    a1.grid(axis="x", alpha=0.3)
    for l in cl:
        c = "#3b6ea5" if l["type"] == "physique" else "#c4793a"
        a2.scatter(l["mu_etoile"], l["sigma"], color=c)
        a2.annotate(l["facteur"], (l["mu_etoile"], l["sigma"]), fontsize=8, xytext=(3, 3), textcoords="offset points")
    m = max(max(l["mu_etoile"] for l in cl), max(l["sigma"] for l in cl if np.isfinite(l["sigma"])) or 0) * 1.05
    a2.plot([0, m], [0, m], ls="--", color="#999", lw=0.8)
    a2.set_xlabel("mu* (influence)")
    a2.set_ylabel("sigma (non-linéarité / interactions)")
    a2.set_title("Au-dessus de la diagonale : effet qui dépend des autres facteurs")
    a2.grid(alpha=0.3)
    fig.suptitle(titre)
    fig.tight_layout()
    f = dossier / f"{nom}_{cle}.png"
    fig.savefig(f, dpi=130)
    plt.close(fig)
    return f


def rapport_md(dossier, meta, analyses, facteurs):
    L = [f"# Étude de Morris — {meta['etiquette']}", "",
         f"- Dates de largage : {', '.join(meta['starts'])} (même météo pour toutes les configs)",
         f"- Facteurs : {len(facteurs)} ({meta['facteurs']}), r = {meta['r']} trajectoires, "
         f"{meta['n_configs']} configs distinctes",
         f"- Runs « pannes » par config : {meta['runs_par_config']} (mêmes graines pour toutes les configs)"
         if "pannes" in meta["modes"] else "- Passe « pannes » non lancée",
         f"- Solutions hors facteurs : {meta['base_solutions']}" if meta["facteurs"] == "physique" else "",
         f"- Durée de calcul : {meta.get('duree_s', 0) / 60:.1f} min", "",
         "**Lecture.** mu* = de combien l'indicateur bouge, en moyenne, quand on monte ce facteur d'un cran "
         "(bas→nominal ou nominal→haut), quels que soient les autres. mu > 0 : monter le facteur augmente "
         "l'indicateur. sigma/mu* > 1 : l'effet dépend fortement des autres facteurs (interactions) ou n'est pas "
         "linéaire. Un intervalle à 90 % de mu* qui touche 0 : effet non distinguable du bruit avec ce r.", "",
         "## Niveaux des facteurs", "", "| Facteur | Description | bas / nominal / haut |", "|---|---|---|"]
    L += [f"| {f['nom']} | {f['desc']} | {libelle_niveaux(f)} |" for f in facteurs]
    for nom_a, analyse in analyses.items():
        mode = nom_a.split("__")[0]
        L += ["", f"## {nom_a.replace('__', ' — ')}"]
        for cle, a in analyse.items():
            principal = cle == INDICATEUR_PRINCIPAL[mode]
            if not principal and cle not in ("p_panne_energie", "jours_arrivee", "jours", "blackouts"):
                continue
            n = None if principal else 10
            L += ["", f"### {a['desc']}" + (" (indicateur principal)" if principal else f" — 10 premiers"), "",
                  "| Rang | Facteur | mu* | IC 90 % | mu (sens) | sigma |", "|---|---|---|---|---|---|"]
            for rg, l in enumerate(a["classement"][:n], 1):
                L.append(f"| {rg} | {l['facteur']} | {_f(l['mu_etoile'])} | [{_f(l['ic90_bas'])} ; "
                         f"{_f(l['ic90_haut'])}] | {_f(l['mu'])} | {_f(l['sigma'])} |")
    f = dossier / "rapport.md"
    f.write_text("\n".join(x for x in L if x is not None) + "\n", encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Enregistrement de toutes les données
# ---------------------------------------------------------------------------
def _json_gz(f, obj):
    with gzip.open(f, "wt", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, default=str)


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _sha_fichiers(fichiers) -> str:
    h = hashlib.sha256()
    for f in fichiers:
        h.update((str(f.relative_to(RACINE)) if f.is_relative_to(RACINE) else f.name).encode("utf-8"))
        with open(f, "rb") as fh:
            for bloc in iter(lambda: fh.read(1 << 20), b""):
                h.update(bloc)
    return h.hexdigest()


EXPLICATION_EMPREINTE = {
    "code_simulateur": "code du simulateur (sim/*.py)",
    "registre_risques": "risks.yaml",
    "configs": "configuration (config.yaml, --base-solutions, --graine, dates)",
    "plan_morris": "plan de Morris (--r, --facteurs, --graine-plan, plages des facteurs)",
    "plan_runs": "runs par config ou graines (--runs, --graine)",
    "meteo": "données météo (grille re-téléchargée ou autre grille)",
}


def empreinte_etude(cfg, configs, trajs, plan_runs, env) -> dict:
    """Tout ce qui détermine les résultats d'un run, et seulement ça.

    Le script d'étude lui-même n'en fait PAS partie (le modifier ne change pas les runs : ses effets passent par
    les configs, comptées ici) ; les passes demandées (--modes) non plus : chaque passe a ses lignes dans le
    checkpoint, on peut lancer « physique » puis « pannes » plus tard dans le même dossier."""
    return {
        "code_simulateur": _sha_fichiers(sorted((RACINE / "sim").rglob("*.py"))),
        "registre_risques": _sha_fichiers([RACINE / "risks.yaml"]),
        "configs": _sha({"base": cfg, "configs": configs}),
        "plan_morris": _sha([{"points": t["points"], "pas": t["pas"]} for t in trajs]),
        "plan_runs": _sha(plan_runs),
        "meteo": _sha_fichiers([Path(env)]),          # contenu, pas la date du fichier
    }


def empreinte_courte(identifiant: dict) -> str:
    return _sha(identifiant)[:8]


class Checkpoint:
    def __init__(self, path, identifiant):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA synchronous = FULL")
        self.conn.execute("CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL)")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS resultats ("
            "mode TEXT NOT NULL, date TEXT NOT NULL, config TEXT NOT NULL, run INTEGER NOT NULL, "
            "donnees BLOB NOT NULL, PRIMARY KEY (mode, date, config, run))")
        courant = self.conn.execute("SELECT valeur FROM meta WHERE cle = 'identifiant'").fetchone()
        texte = json.dumps(identifiant, sort_keys=True)
        if courant and courant[0] != texte:
            self.conn.close()
            try:
                ancien = json.loads(courant[0])
                change = [EXPLICATION_EMPREINTE.get(k, k) for k in sorted(set(ancien) | set(identifiant))
                          if ancien.get(k) != identifiant.get(k)]
            except (ValueError, AttributeError):
                change = ["format du checkpoint"]
            raise SystemExit(
                f"Checkpoint incompatible : {path}\n  a changé depuis le début de l'étude : {', '.join(change)}\n"
                "  Reprendre : remettre les choses comme avant. Nouvelle étude : une autre --etiquette "
                "(ou aucune : le nom par défaut contient l'empreinte).")
        if not courant:
            self.conn.execute("INSERT INTO meta VALUES ('identifiant', ?)", (texte,))
            self.conn.commit()

    def contient(self, mode, date, config, run):
        return self.conn.execute(
            "SELECT 1 FROM resultats WHERE mode = ? AND date = ? AND config = ? AND run = ?",
            (mode, date, config, run)).fetchone() is not None

    def enregistrer(self, mode, date, config, run, resultat):
        donnees = gzip.compress(json.dumps(resultat, ensure_ascii=False, default=str).encode("utf-8"))
        self.conn.execute(
            "INSERT OR REPLACE INTO resultats VALUES (?, ?, ?, ?, ?)",
            (mode, date, config, run, donnees))
        self.conn.commit()

    def lire(self, mode):
        lignes = self.conn.execute(
            "SELECT date, config, run, donnees FROM resultats WHERE mode = ? ORDER BY date, config, run",
            (mode,))
        return [(date, config, run, json.loads(gzip.decompress(donnees)))
                for date, config, run, donnees in lignes]

    def fermer(self):
        self.conn.close()


def version_code():
    """Commit git (+ « -modifie » si l'arbre n'est pas propre) : pour savoir quel code a produit les données."""
    import subprocess
    try:
        h = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RACINE, capture_output=True, text=True).stdout.strip()
        sale = subprocess.run(["git", "status", "--porcelain", "--", "sim", "main.py", "config.yaml", "risks.yaml"],
                              cwd=RACINE, capture_output=True, text=True).stdout.strip()
        return h + ("-modifie" if sale else "")
    except OSError:
        return "inconnu"


def niveaux_config(facteurs, x):
    """{facteur: niveau lisible} pour un point de la grille."""
    out = {}
    for f, xi in zip(facteurs, x):
        n = int(round(float(xi) * 2))
        out[f["nom"]] = NIVEAUX_SOLUTION[n] if f["type"] == "solution" else ("bas", "nominal", "haut")[n]
    return out


PIDS = [f"P{i}" for i in range(1, 29)]


def sauver_runs(dossier, mode, bruts, niveaux, facteurs):
    """runs_<mode>.json.gz : chaque run complet (trace, occurrences P1–P28, premières apparitions, stats…).
    runs_<mode>.csv : une ligne par run, colonnes plates (niveaux des facteurs + résultats), pour tableur/pandas."""
    _json_gz(dossier / f"runs_{mode}.json.gz", bruts)
    noms_f = [f["nom"] for f in facteurs]
    lignes = []
    for b in bruts:
        l = {"date": b["date"], "config": b["config"], **{f"f_{n}": niveaux[b["config"]][n] for n in noms_f}}
        if mode == "pannes":
            for k in ("jeu", "graine", "fin", "cause_pid", "issue_physique", "retrouve", "jours_fin",
                      "dist_restante_nm", "lat_fin_mission", "lon_fin_mission", "lat_fin", "lon_fin",
                      "premier_probleme", "blackouts", "hors_boite", "e_solaire", "e_moteur", "e_chauffage"):
                l[k] = b.get(k)
            for p in PIDS:
                l[f"occ_{p}"] = b.get("occurrences", {}).get(p, 0)
                l[f"j1_{p}"] = b.get("premiere_j", {}).get(p)
        else:
            l.update({"fin": b.get("fin"), "jours": b.get("jours"), "reste_nm": b.get("reste_nm")})
            l.update({f"stat_{k}": v for k, v in sorted(b.get("stats", {}).items())})
        lignes.append(l)
    cols = list(dict.fromkeys(k for l in lignes for k in l))
    with open(dossier / f"runs_{mode}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(lignes)


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------
def chemin_grille(cfg):
    from sim import environment as E
    f = E.chemin_grille(cfg, strict=False)
    if f is not None:
        return f
    if (C.DATA / "grille_2deg_partiel.npz").exists():
        print("ATTENTION : grille partielle (téléchargement incomplet).")
        return C.DATA / "grille_2deg_partiel.npz"
    raise SystemExit("Aucune grille météo : lancer d'abord « python3 main.py donnees ».")


def avec_start(cfg, start):
    c = copy.deepcopy(cfg)
    c["mission"]["start"] = start if "T" in start else f"{start}T12:00:00Z"
    return c


def analyser_tout(trajs, labels, Y, facteurs, modes, starts, dossier):
    analyses = {}
    for mode in modes:
        noms = list(starts) + (["moyenne"] if len(starts) > 1 else [])
        for s in noms:
            if s == "moyenne":         # indicateur moyen sur les dates, config par config
                Ys = {lab: {cle: _moy([Y[mode][d][lab].get(cle) for d in starts]) for cle, _, _ in INDICATEURS[mode]}
                      for lab in labels.values()}
            else:
                Ys = Y[mode][s]
            a = analyser(trajs, labels, Ys, facteurs, mode)
            nom = f"{mode}__{s}"
            analyses[nom] = a
            ecrire_csv(dossier, nom, a)
            figure(dossier, nom, a, INDICATEUR_PRINCIPAL[mode], f"Morris — passe {mode} — {s}")
    return analyses


def afficher(analyses, n=10):
    for nom, a in analyses.items():
        mode = nom.split("__")[0]
        cle = INDICATEUR_PRINCIPAL[mode]
        print(f"\n== {nom.replace('__', ' — ')} : {a[cle]['desc']} ==")
        print(f"   {'facteur':14s} {'mu*':>9s} {'IC90':>21s} {'mu':>9s} {'sigma':>9s}")
        for l in a[cle]["classement"][:n]:
            print(f"   {l['facteur']:14s} {_f(l['mu_etoile']):>9s} [{_f(l['ic90_bas']):>8s};{_f(l['ic90_haut']):>9s}] "
                  f"{_f(l['mu']):>9s} {_f(l['sigma']):>9s}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Étude de sensibilité de Morris sur la conception du bateau")
    p.add_argument("--config", default=None, help="fichier de configuration (défaut config.yaml)")
    p.add_argument("--start", default=None, help="date de largage AAAA-MM-JJ (défaut : celle de la config)")
    p.add_argument("--starts", default=None, help="plusieurs dates séparées par des virgules (+ moyenne)")
    p.add_argument("--r", type=int, default=10, help="nombre de trajectoires de Morris (défaut 10)")
    p.add_argument("--runs", type=int, default=None,
                   help="runs « pannes » par config (défaut : jeux_parametres de risks.yaml, 25 ; minimum 25)")
    p.add_argument("--facteurs", choices=["tous", "physique", "solutions"], default="tous")
    p.add_argument("--base-solutions", choices=["config", "absente", "partielle", "validee"], default="partielle",
                   help="état des S1–S20 quand elles ne sont pas des facteurs (--facteurs physique)")
    p.add_argument("--modes", default="physique,pannes", help="passes à lancer : physique, pannes ou les deux")
    p.add_argument("--graine", type=int, default=None, help="graine des runs (défaut : simulation.graine)")
    p.add_argument("--graine-plan", type=int, default=1, help="graine du plan de Morris")
    p.add_argument("--processus", type=int, default=None)
    p.add_argument("--etiquette", default=None, help="nom du dossier de sortie dans out/morris/")
    p.add_argument("--plan", action="store_true", help="affiche la taille du plan et s'arrête")
    p.add_argument("--analyser", default=None, help="dossier d'une étude déjà faite : ré-analyse seulement")
    a = p.parse_args(argv)

    if a.analyser:
        d = Path(a.analyser)
        donnees = json.loads((d / "brut.json").read_text(encoding="utf-8"))
        meta = donnees["meta"]
        facteurs = donnees["facteurs"]
        trajs = [{"points": [tuple(x) for x in t["points"]], "pas": [tuple(s) for s in t["pas"]]}
                 for t in donnees["trajectoires"]]
        labels = points_uniques(trajs)
        analyses = analyser_tout(trajs, labels, donnees["Y"], facteurs, meta["modes"], meta["starts"], d)
        afficher(analyses)
        print("\n", rapport_md(d, meta, analyses, facteurs))
        return 0

    cfg = C.charger(a.config)
    if a.graine is not None:
        cfg["simulation"]["graine"] = a.graine
    if a.facteurs == "physique" and a.base_solutions != "config":
        for s in cfg["solutions"]:
            cfg["solutions"][s] = a.base_solutions
    starts = [s.strip() for s in a.starts.split(",")] if a.starts else [a.start or cfg["mission"]["start"][:10]]
    modes = [m.strip() for m in a.modes.split(",") if m.strip()]
    facteurs = construire_facteurs(cfg, a.facteurs)
    trajs = plan_morris(len(facteurs), a.r, a.graine_plan)
    labels = points_uniques(trajs)
    runs_cfg = len(MC.plan(cfg, a.runs or 0))
    n_phys = len(labels) * len(starts) if "physique" in modes else 0
    n_pan = len(labels) * len(starts) * runs_cfg if "pannes" in modes else 0
    print(f"{len(facteurs)} facteurs, r = {a.r} -> {len(labels)} configs distinctes × {len(starts)} date(s)")
    print(f"  passe physique : {n_phys} missions ; passe pannes : {n_pan} missions ({runs_cfg} runs/config)")
    if a.plan:
        return 0

    env = chemin_grille(cfg)
    configs = {d: {lab: avec_start(appliquer(cfg, facteurs, x), d) for x, lab in labels.items()} for d in starts}
    niveaux = {lab: niveaux_config(facteurs, x) for x, lab in labels.items()}
    plan_runs = MC.plan(cfg, a.runs or 0)
    print("Empreinte de l'étude (code, météo, plan)…")
    identifiant = empreinte_etude(cfg, configs, trajs, plan_runs, env)
    # nom par défaut : dates + facteurs + empreinte courte -> même étude = même dossier (reprise),
    # étude différente (autre --r, --runs, graine, code, météo…) = nouveau dossier, jamais de mélange
    etq = a.etiquette or ("_".join(s.replace("-", "") for s in starts) + f"_{a.facteurs}_"
                          + empreinte_courte(identifiant))
    dossier = C.OUT / "morris" / etq
    dossier.mkdir(parents=True, exist_ok=True)
    checkpoint_path = dossier / "checkpoint.sqlite3"
    checkpoint = Checkpoint(checkpoint_path, identifiant)
    print(f"Auto-save actif : {checkpoint_path} (reprise automatique)")
    # tout ce qui définit l'étude, écrit AVANT de simuler : config de base, plan, config complète de chaque cas
    _json_gz(dossier / "configs.json.gz", {
        "config_base": cfg, "grille_meteo": str(env), "version_code": version_code(),
        "facteurs": facteurs, "niveaux": niveaux, "configs": configs})
    Y = {m: {} for m in modes}
    t0 = time.time()
    if "physique" in modes:
        print("Passe physique…")
        liste = [(d, lab, c) for d in starts for lab, c in configs[d].items()
                 if not checkpoint.contient("physique", d, lab, 0)]

        def sauvegarder_physique(i, resultat):
            d, lab, _ = liste[i]
            checkpoint.enregistrer("physique", d, lab, 0, resultat)

        if liste:
            MC.lancer_physique([c for _, _, c in liste], env, processus=a.processus,
                               on_result=sauvegarder_physique)
        bruts = []
        for d, lab, _, resultat in checkpoint.lire("physique"):
            Y["physique"].setdefault(d, {})[lab] = indicateurs_physique(resultat)
            bruts.append({"date": d, "config": lab, **resultat})
        sauver_runs(dossier, "physique", bruts, niveaux, facteurs)
        print(f"  fait ({time.time() - t0:.0f} s), runs enregistrés")
    if "pannes" in modes:
        print("Passe pannes…")
        demandes = {}
        etapes = {}
        plans_restant = {}
        for d in starts:
            configs_restantes = {}
            for lab, c in configs[d].items():
                manquants = []
                signature = json.dumps(c, sort_keys=True, default=str)
                for i, (jeu, graine) in enumerate(plan_runs):
                    if not checkpoint.contient("pannes", d, lab, i):
                        manquants.append((jeu, graine))
                        demandes.setdefault((signature, jeu, graine), []).append((d, lab, i))
                if manquants:
                    configs_restantes[lab] = c
                    plans_restant[(d, lab)] = manquants
            if configs_restantes:
                etapes[d] = (configs_restantes, runs_cfg)

        def sauvegarder_panne(cle, resultat):
            for d, lab, i in demandes[cle]:
                resultat_config = dict(resultat)
                resultat_config["etiquette"] = lab
                checkpoint.enregistrer("pannes", d, lab, i, resultat_config)

        if etapes:
            MC.lancer_lot(etapes, env, processus=a.processus, on_result=sauvegarder_panne,
                          plans=plans_restant)
        bruts = []
        par_config = {}
        for d, lab, i, resultat in checkpoint.lire("pannes"):
            par_config.setdefault((d, lab), []).append((i, resultat))
            bruts.append({"date": d, "config": lab, **resultat})
        for d in starts:
            Y["pannes"][d] = {}
            for lab in configs[d]:
                runs = [r for _, r in sorted(par_config[(d, lab)])]
                Y["pannes"][d][lab] = indicateurs_pannes(runs)
        sauver_runs(dossier, "pannes", bruts, niveaux, facteurs)
        print("  runs enregistrés")
    checkpoint.fermer()
    meta = {"etiquette": etq, "starts": starts, "modes": modes, "facteurs": a.facteurs, "r": a.r,
            "n_configs": len(labels), "runs_par_config": runs_cfg, "graine_plan": a.graine_plan,
            "graine_runs": cfg["simulation"]["graine"], "base_solutions": a.base_solutions,
            "duree_s": time.time() - t0, "version_code": version_code(), "grille_meteo": str(env),
            "commande": " ".join(sys.argv)}
    (dossier / "brut.json").write_text(json.dumps(
        {"meta": meta, "facteurs": facteurs,
         "trajectoires": [{"points": [list(x) for x in t["points"]], "pas": t["pas"]} for t in trajs],
         "configs": {lab: list(x) for x, lab in labels.items()}, "Y": Y}, ensure_ascii=False, default=str),
        encoding="utf-8")
    analyses = analyser_tout(trajs, labels, Y, facteurs, modes, starts, dossier)
    afficher(analyses)
    print(f"\nRapport : {rapport_md(dossier, meta, analyses, facteurs)}")
    print(f"Tout est dans {dossier}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
