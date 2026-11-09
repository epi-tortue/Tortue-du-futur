"""Figures et tableaux du Monte-Carlo, contrefactuels, rapport final (Markdown)."""
from __future__ import annotations

from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import montecarlo as MC  # noqa: E402
from .config import OUT  # noqa: E402
from .journal import FINS  # noqa: E402

# palette de référence (dataviz) : ordre fixe ; gris pour « autres »
SERIE = ["#2a78d6", "#eb6834", "#1baf7a"]
NEUTRE = "#9a9893"
ENCRE = "#0b0b0b"
ENCRE2 = "#52514e"
GRILLE = "#e4e3df"


def _style(ax):
    ax.grid(axis="x", color=GRILLE, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRILLE)
    ax.tick_params(colors=ENCRE2, labelsize=9)


def pct(x):
    if abs(x) < 0.0005:
        x = 0.0
    return f"{100 * x:.0f} %" if x >= 0.995 or x <= 0.005 or 100 * x >= 10 else f"{100 * x:.1f} %"


def ic(t):
    est, lo, hi = t
    return f"{pct(est)} [{pct(lo)} – {pct(hi)}]"


# ---------------------------------------------------------------------------
def figure_issues(runs, nom, titre):
    iss = MC.issues(runs)
    ordre = sorted(iss, key=lambda k: -iss[k][0])
    est = np.array([iss[k][0] for k in ordre])
    lo = np.array([iss[k][1] for k in ordre])
    hi = np.array([iss[k][2] for k in ordre])
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(ordre) + 1.4), constrained_layout=True)
    y = np.arange(len(ordre))[::-1]
    ax.barh(y, 100 * est, height=0.55, color=SERIE[0])
    ax.errorbar(100 * est, y, xerr=[100 * (est - lo), 100 * (hi - est)], fmt="none", ecolor=ENCRE, elinewidth=1,
                capsize=3)
    ax.set_yticks(y, [FINS.get(k, k) for k in ordre], fontsize=9, color=ENCRE)
    for yi, e, h in zip(y, est, hi):
        ax.text(100 * h + 1, yi, pct(e), va="center", fontsize=8, color=ENCRE2)
    ax.set_xlabel("probabilité (%) — barre : estimation ; trait : intervalle à 90 %", color=ENCRE2, fontsize=9)
    ax.set_xlim(0, min(100, 100 * hi.max() + 12))
    _style(ax)
    ax.set_title(titre, fontsize=11, color=ENCRE, loc="left")
    f = OUT / f"{nom}.png"
    fig.savefig(f, dpi=120)
    plt.close(fig)
    return str(f)


def figure_jours(runs, nom, titre):
    j = np.array([r["jours_fin"] for r in runs])
    succes = np.array([r["fin"] == "arrivee" for r in runs])
    fig, ax = plt.subplots(figsize=(9, 3.4), constrained_layout=True)
    bins = np.linspace(0, max(10, j.max()) + 1, 40)
    ax.hist([j[~succes], j[succes]], bins=bins, stacked=True, color=[NEUTRE, SERIE[0]],
            label=["mission terminée sans arriver", "arrivée"], edgecolor="white", linewidth=1)
    ax.set_xlabel("jour de fin de mission", color=ENCRE2, fontsize=9)
    ax.set_ylabel("nombre de runs", color=ENCRE2, fontsize=9)
    ax.grid(axis="y", color=GRILLE, lw=0.8)
    ax.legend(fontsize=8, frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_title(titre + f" — médiane {np.median(j):.0f} j", fontsize=11, color=ENCRE, loc="left")
    f = OUT / f"{nom}.png"
    fig.savefig(f, dpi=120)
    plt.close(fig)
    return str(f)


def figure_positions_finales(cfg, runs, nom, titre):
    from .environment import charger_cote
    from .report import _decor
    terre, _ = charger_cote()
    cadre = (-58, 41, -4, 59)
    cpt = Counter(r["fin"] for r in runs)
    principales = [k for k, _ in cpt.most_common(3)]
    fig, ax = plt.subplots(figsize=(12, 6.5), constrained_layout=True)
    for r in runs[:300]:
        tr = np.array(r["trace"])
        ax.plot(tr[:, 1], tr[:, 0], color=NEUTRE, lw=0.3, alpha=0.35, zorder=2)
    for k, issue in enumerate(principales + ["autres"]):
        sel = [r for r in runs if (r["fin"] == issue if issue != "autres" else r["fin"] not in principales)]
        if not sel:
            continue
        c = SERIE[k] if issue != "autres" else NEUTRE
        ax.scatter([r["lon_fin_mission"] for r in sel], [r["lat_fin_mission"] for r in sel], s=14, color=c,
                   edgecolors="white", linewidths=0.6, zorder=8,
                   label=f"{FINS.get(issue, issue) if issue != 'autres' else 'autres issues'} ({len(sel)})")
    _decor(ax, cfg, terre, cadre)
    ax.legend(loc="lower right", fontsize=8, frameon=True)
    ax.set_title(titre + " — positions en fin de mission (traits gris : trajectoires)", fontsize=11, loc="left")
    f = OUT / f"{nom}.png"
    fig.savefig(f, dpi=110)
    plt.close(fig)
    return str(f)


def figure_valeur_solutions(gains: dict, nom, titre, xlabel):
    """gains : {Sx: (est, lo, hi)} en points de probabilité."""
    ordre = sorted(gains, key=lambda k: gains[k][0])
    est = np.array([gains[k][0] for k in ordre])
    lo = np.array([gains[k][1] for k in ordre])
    hi = np.array([gains[k][2] for k in ordre])
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(ordre) + 1.4), constrained_layout=True)
    y = np.arange(len(ordre))
    ax.barh(y, 100 * est, height=0.55, color=SERIE[0])
    ax.errorbar(100 * est, y, xerr=[100 * (est - lo), 100 * (hi - est)], fmt="none", ecolor=ENCRE, elinewidth=1,
                capsize=3)
    ax.axvline(0, color=ENCRE2, lw=0.8)
    ax.set_yticks(y, [f"{k} {NOMS_S.get(k, '')}" for k in ordre], fontsize=8, color=ENCRE)
    ax.set_xlabel(xlabel, color=ENCRE2, fontsize=9)
    _style(ax)
    ax.set_title(titre, fontsize=11, color=ENCRE, loc="left")
    f = OUT / f"{nom}.png"
    fig.savefig(f, dpi=120)
    plt.close(fig)
    return str(f)


NOMS_S = {"S1": "coque ailes inondables", "S2": "couplage magnétique", "S3": "motorisation brushless",
          "S4": "protection hélice", "S5": "barre robuste/redondante", "S6": "double circuit énergie",
          "S7": "bilan énergétique", "S8": "gestion d'énergie", "S9": "étanchéité & CEM",
          "S10": "architecture logicielle", "S11": "watchdog", "S12": "navigation ArduPilot",
          "S13": "validation SITL", "S14": "liaison satellite", "S15": "AIS & visibilité", "S16": "anti-filets",
          "S17": "anti-fouling", "S18": "balise de survie", "S19": "stratégie de route",
          "S20": "démarche progressive"}


# ---------------------------------------------------------------------------
def tableau_problemes(reg, base_runs, cf_runs: dict) -> list[str]:
    """P(survient) et P(met fin à la mission), sans et avec la solution principale validée."""
    L = ["| Problème | Solution principale | P(survient) sans | P(survient) avec | P(met fin) sans | P(met fin) avec |",
         "|---|---|---|---|---|---|"]
    for pid, P in reg["problemes"].items():
        s = P["solutions"][0]
        avec = cf_runs.get(s)
        occ = lambda r, p=pid: r["occurrences"].get(p, 0) > 0  # noqa: E731
        fin = lambda r, p=pid: r["cause_pid"] == p  # noqa: E731
        a = MC.bootstrap(base_runs, occ)
        b = MC.bootstrap(avec, occ) if avec else None
        c = MC.bootstrap(base_runs, fin)
        d = MC.bootstrap(avec, fin) if avec else None
        if pid == "P19":
            L.append(f"| **{pid}** {P['titre']} | {s} | effet global : × taux des domaines B–G | | | |")
            continue
        L.append(f"| **{pid}** {P['titre']} | {s} | {ic(a)} | {ic(b) if b else '(déjà validée)'} | {ic(c)} | "
                 f"{ic(d) if d else '(déjà validée)'} |")
    return L


def gains_solutions(cf: dict, f) -> dict:
    ref = cf["reference"]
    return {s: MC.bootstrap_diff(ref, runs, f) for s, runs in cf.items() if s != "reference"}
