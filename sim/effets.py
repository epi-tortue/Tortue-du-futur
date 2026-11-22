"""Étude d'effets : que change chaque correction du modèle, sur les mêmes graines ?

Chaque correction garde l'ancien comportement comme option. On part de l'ancien modèle
(toutes les corrections désactivées) et on les active une à une, dans l'ordre, en cumulant.
À chaque étape on mesure, avec les mêmes graines et les mêmes jeux de paramètres :
  - P(arrivée) du bateau actuel et du bateau « tout validé », départ d'hiver ;
  - les mêmes, départ d'été ;
  - le classement des solutions (perte de P(arrivée) quand on retire Sx d'un bateau tout validé).

    python main.py effets [--runs N] [--runs-cf N]      -> out/effets_<date>.md
"""
from __future__ import annotations

import copy
import time

from . import montecarlo as MC
from . import rapport_mc as RM
from .config import DATA, OUT

# (identifiant, libellé, surcharges qui RÉTABLISSENT l'ancien comportement)
CORRECTIONS = [
    ("chavirage", "1. Chavirage lié à la cambrure des vagues [H71]",
     {"registre_surcharges": {"problemes": {"P2": {"chavirage": {"modele": "hs4"}}}}}),
    ("p9", "2. P9 : lacets (pilotage) séparés de la résistance des vagues [H72]",
     {"registre_surcharges": {"problemes": {"P9": {"modele": "puissance"}}}}),
    ("s8", "3. Gestion d'énergie S8 par prévision solaire [H74]",
     {"energie": {"validee": {"politique": "regulation"}}, "navigation": {"derive_veille_max_ms": 0.0}}),
    ("approche", "5. Approche par le bord sud du cercle [H75]",
     {"navigation": {"approche": {"strategie": "centre"}}}),
    ("gps", "6. Marge de saut sur le fix GPS [H34]",
     {"navigation": {"gps_marge_saut_m": 0.0}}),
]


def _fusion(base: dict, sur: dict) -> dict:
    for k, v in sur.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _fusion(base[k], v)
        else:
            base[k] = copy.deepcopy(v)
    return base


def config_etape(cfg: dict, n_actives: int) -> dict:
    """Configuration où seules les `n_actives` premières corrections sont actives."""
    c = copy.deepcopy(cfg)
    for _, _, ancien in CORRECTIONS[n_actives:]:
        _fusion(c, ancien)
    return c


def config_ancienne(cfg: dict) -> dict:
    """Ancien modèle : toutes les corrections désactivées (sert au test de non-régression)."""
    return config_etape(cfg, 0)


def _tout(cfg, etat="validee"):
    c = copy.deepcopy(cfg)
    for s in c["solutions"]:
        c["solutions"][s] = etat
    return c


def mesurer(cfg, n_runs, n_cf, chemin_env, journal=print) -> dict:
    """Résultats clés d'une configuration : arrivées hiver / été et classement des solutions."""
    succes = lambda r: r["fin"] == "arrivee"  # noqa: E731
    ce = copy.deepcopy(cfg)
    ce["mission"]["start"] = cfg["mission"]["comparaison_ete"]
    etapes = {"mc": ({"actuel": cfg, "tout_valide": _tout(cfg), "ete_actuel": ce, "ete_tout_valide": _tout(ce)},
                     n_runs)}
    if n_cf:
        etapes["cf"] = (MC.configs_contrefactuelles(cfg, "retrait"), n_cf)
    lot = MC.lancer_lot(etapes, chemin_env, journal=lambda *_: None)       # un pool, runs communs calculés une fois
    res = lot["mc"]
    out = {k: MC.bootstrap(v, succes) for k, v in res.items()}
    out["chavire_tout_valide"] = MC.bootstrap(res["tout_valide"], lambda r: r["fin"] == "chavire")
    out["capture_actuel"] = MC.bootstrap(res["actuel"], lambda r: r["fin"] in ("capture", "perdu_filet"))
    out["jours_median_tout_valide"] = float(sorted(r["jours_fin"] for r in res["tout_valide"])[len(res["tout_valide"]) // 2])
    if n_cf:
        cf = lot["cf"]
        ref = cf["reference"]
        out["retrait"] = {s: MC.bootstrap_diff(runs, ref, succes) for s, runs in cf.items() if s != "reference"}
    return out


def etudier(cfg, n_runs, n_cf, chemins: dict, journal=print) -> str:
    """chemins : {"2deg": Path, "1deg": Path ou None}. Écrit out/effets_<date>.md et retourne son chemin."""
    et = cfg["mission"]["start"][:10].replace("-", "")
    etapes = [("Ancien modèle (avant corrections)", config_etape(cfg, 0), chemins["2deg"])]
    for i, (_, lib, _) in enumerate(CORRECTIONS):
        etapes.append((lib, config_etape(cfg, i + 1), chemins["2deg"]))
    if chemins.get("1deg"):
        etapes.append(("9. Grille météo à 1° (au lieu de 2°)", copy.deepcopy(cfg), chemins["1deg"]))
    mesures = []
    for lib, c, chemin in etapes:
        t0 = time.time()
        mesures.append(mesurer(c, n_runs, n_cf, chemin))
        journal(f"  {lib} : {time.time() - t0:.0f} s — hiver actuel {RM.ic(mesures[-1]['actuel'])}, "
                f"tout validé {RM.ic(mesures[-1]['tout_valide'])}")
    L = [f"# Effet de chaque correction du modèle — départ {cfg['mission']['start'][:10]}", "",
         f"Corrections activées une à une, en cumulant, sur les mêmes graines ({n_runs} runs par configuration, "
         f"{n_cf} pour le classement des solutions). Intervalles à 90 %. Une ligne se lit par rapport à la "
         "précédente. Les points 4 (pêche), 7 (années de météo) et 8 (icebergs) ne changent pas le modèle par "
         "défaut : ils sont traités dans le rapport.", "",
         "| Étape | Hiver : actuel | Hiver : tout validé | Été : actuel | Été : tout validé | "
         "Hiver, tout validé : resté chaviré | Hiver, tout validé : jour de fin médian |", "|---|---|---|---|---|---|---|"]
    for (lib, _, _), m in zip(etapes, mesures):
        L.append(f"| {lib} | {RM.ic(m['actuel'])} | {RM.ic(m['tout_valide'])} | {RM.ic(m['ete_actuel'])} | "
                 f"{RM.ic(m['ete_tout_valide'])} | {RM.ic(m['chavire_tout_valide'])} | "
                 f"{m.get('jours_median_tout_valide', float('nan')):.0f} |")
    if n_cf:
        L += ["", "## Classement des solutions (perte de P(arrivée) si on retire Sx d'un bateau tout validé)", "",
              "Les cinq premières à chaque étape, avec la perte en points de probabilité.", "",
              "| Étape | 1 | 2 | 3 | 4 | 5 | Rang et valeur de S5 | Rang et valeur de S8 |", "|---|---|---|---|---|---|---|---|"]
        for (lib, _, _), m in zip(etapes, mesures):
            # bootstrap_diff(sans Sx, référence) = E[référence] − E[sans Sx] : la perte est POSITIVE
            ordre = sorted(m["retrait"], key=lambda s: -m["retrait"][s][0])
            top = " | ".join(f"{s} ({RM.pct(m['retrait'][s][0])})" for s in ordre[:5])
            rang = lambda s: f"{ordre.index(s) + 1}ᵉ ({RM.pct(m['retrait'][s][0])})"  # noqa: E731
            L.append(f"| {lib} | {top} | {rang('S5')} | {rang('S8')} |")
    # 3. politique d'énergie S8 : comparaison directe, navigation parfaite et sans pannes [H74]
    from . import analyse_energie as AE
    from . import story
    ctx = story.Contexte(chemins.get("1deg") or chemins["2deg"])
    L += ["", "## Gestion d'énergie S8 : politiques comparées (sans pannes, navigation parfaite)", "",
          "12 largages décalés de 12 h ; « naïve » = S8 absente (moteur à fond jusqu'à la coupure du BMS). "
          "« prevision » = prévision parfaite (rayonnement réel des 24 h suivantes) ; « prevision_persistance » = "
          "ce que le bateau peut prévoir seul (demain comme aujourd'hui). Critère : la politique validée doit faire "
          "au moins aussi bien que la naïve (arrivées, puis distance restante)."]
    for nom_s, d in (("hiver", cfg["mission"]["start"]), ("été", cfg["mission"]["comparaison_ete"])):
        r = AE.comparer(cfg, ctx, d)
        L += ["", f"**Départ {d[:10]} ({nom_s})**", ""] + AE.tableau(r)
        journal(f"  S8 {nom_s} : " + ", ".join(f"{k} {v['arrivees']}/{v['n']}" for k, v in r.items()))
    OUT.mkdir(exist_ok=True)
    f = OUT / f"effets_{et}.md"
    f.write_text("\n".join(L), encoding="utf-8")
    import json
    (OUT / f"effets_{et}.json").write_text(json.dumps(
        [{"etape": lib, "mesures": m} for (lib, _, _), m in zip(etapes, mesures)], ensure_ascii=False),
        encoding="utf-8")
    journal(f"Étude d'effets : {f}")
    return str(f)


def chemins_grilles() -> dict:
    return {"2deg": DATA / "grille_2deg.npz",
            "1deg": DATA / "grille_1deg.npz" if (DATA / "grille_1deg.npz").exists() else None}
