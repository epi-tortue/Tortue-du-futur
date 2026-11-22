"""Rapport final : Monte-Carlo, contrefactuels, tableau P1–P28, histoire la plus probable,
récits « et si », comparaison de saison, chauffage. Écrit out/rapport_<date>.md."""
from __future__ import annotations

import copy
import time
from collections import Counter

from . import carte, journal as JB, report
from . import rapport_mc as RM
from . import montecarlo as MC
from .config import OUT
from .journal import FINS


def _tout(cfg, etat="validee"):
    c = copy.deepcopy(cfg)
    for s in c["solutions"]:
        c["solutions"][s] = etat
    return c


def _rel(f):
    return str(f).replace(str(OUT) + "\\", "").replace(str(OUT) + "/", "").replace("\\", "/")


def MC_PROCESSUS(cfg):
    import os
    return cfg["simulation"].get("processus") or max(1, (os.cpu_count() or 2) - 2)


def inclure(nom: str, titre: str | None = None) -> list[str]:
    """Contenu d'un fichier Markdown de out/ (étude séparée), titres décalés d'un niveau ; [] s'il manque."""
    f = OUT / nom
    if not f.exists():
        return []
    lignes = f.read_text(encoding="utf-8").splitlines()
    out = []
    for i, x in enumerate(lignes):
        if i == 0 and x.startswith("# "):
            out.append("### " + (titre or x[2:]))
            continue
        out.append(("##" + x) if x.startswith("#") else x)
    return ["", *out]


def section_corrections(et: str) -> list[str]:
    """Section 11 : effet de chaque correction du modèle et études associées (fichiers produits par
    python main.py effets / peche / annees ; absents = étude non lancée)."""
    L = ["", "## 11. Corrections du modèle (novembre 2026) : effet mesuré", "",
         "Chaque correction garde l'ancien comportement comme option (HYPOTHESES.md, H71–H78). Elles sont "
         "activées une à une, sur les mêmes graines et les mêmes jeux de paramètres, pour mesurer ce que chacune "
         "change aux résultats clés. Les écarts plus petits que les intervalles à 90 % ne sont pas significatifs."]
    L += inclure(f"effets_{et}.md", "Effet de chaque correction (python main.py effets)")
    L += inclure(f"peche_{et}.md", "Captures par les pêcheurs : effet de la route (python main.py peche)")
    L += inclure(f"annees_{et}.md", "Plusieurs années de météo (python main.py annees)")
    L += ["", "### Icebergs", "",
          "Module désactivé par défaut : les observations 2026 de l'International Ice Patrol ne sont pas en libre "
          "accès, et aucune donnée n'est inventée (H08, H77). Le README donne le format de `data/icebergs.csv` et "
          "la façon d'obtenir les données (NSIDC G00807, compte Earthdata).",
          "", "### Mode d'arrondi (H78)", "",
          "`import codac` laissait le processeur en arrondi vers le haut pour tout le simulateur, mais seulement à "
          "partir de son premier import dans chaque processus : le premier run de chaque processus du Monte-Carlo "
          "était calculé un peu différemment des autres. Le simulateur calcule désormais au plus proche, et vers "
          "le haut seulement pendant les calculs Codac. Effet physique nul ; résultats reproductibles quel que soit "
          "l'ordre d'exécution des runs."]
    return L


def generer(cfg, n_runs, n_cf, chemin_env, ete=True, journal=print):
    t_debut = time.time()
    et = cfg["mission"]["start"][:10].replace("-", "")
    date = cfg["mission"]["start"][:10]
    OUT.mkdir(exist_ok=True)
    R = {}

    # 1–3. Tous les Monte-Carlo du rapport, dans un seul pool de processus (mêmes graines et mêmes résultats
    #      que des appels séparés ; les runs communs à plusieurs étapes ne sont calculés qu'une fois)
    journal(f"[1-3/7] Monte-Carlo : actuel et « tout validé » ({n_runs} runs), contrefactuels « + Sx » et "
            f"« tout validé − Sx » ({n_cf} runs par configuration), saison, calibration")
    ce = copy.deepcopy(cfg)
    ce["mission"]["start"] = cfg["mission"]["comparaison_ete"]
    ch = _tout(cfg, "partielle")
    ch["mission"]["start"] = cfg["mission"]["comparaison_ete"]
    etapes = {"reference": ({"actuel": cfg, "tout_valide": _tout(cfg)}, n_runs),
              "cf_ajout": (MC.configs_contrefactuelles(cfg, "ajout"), n_cf),
              "cf_retrait": (MC.configs_contrefactuelles(cfg, "retrait"), n_cf),
              "calibration": ({"historique": ch}, 200)}
    if ete:
        etapes["ete"] = ({"actuel": ce, "tout_valide": _tout(ce)}, max(100, n_runs // 2))
    t_mc = time.time()
    lot = MC.lancer_lot(etapes, chemin_env, journal=journal)
    journal(f"  Monte-Carlo terminés en {(time.time() - t_mc) / 60:.1f} min")
    chrono = {"monte_carlo": time.time() - t_mc}
    res, cf_aj, cf_re = lot["reference"], lot["cf_ajout"], lot["cf_retrait"]
    MC.sauver(res, f"reference_{et}")
    MC.sauver(cf_aj, f"cf_ajout_{et}")
    MC.sauver(cf_re, f"cf_retrait_{et}")
    base, best = res["actuel"], res["tout_valide"]
    res_ete = None
    if ete:
        res_ete = lot["ete"]
        MC.sauver(res_ete, f"ete_{ce['mission']['start'][:10].replace('-', '')}")
    calib = lot["calibration"]["historique"]
    t_etape = time.time()

    # 4. figures
    journal("[4/7] Figures")
    figs = {
        "issues": RM.figure_issues(base, f"mc_issues_{et}", f"Issues — configuration actuelle, départ {date} ({len(base)} runs)"),
        "issues_best": RM.figure_issues(best, f"mc_issues_toutvalide_{et}", f"Issues — toutes solutions validées, départ {date}"),
        "jours": RM.figure_jours(base, f"mc_jours_{et}", "Jour de fin de mission (configuration actuelle)"),
        "jours_best": RM.figure_jours(best, f"mc_jours_toutvalide_{et}", "Jour de fin de mission (tout validé)"),
        "pos": RM.figure_positions_finales(cfg, base, f"mc_positions_{et}", f"Configuration actuelle, départ {date}"),
        "pos_best": RM.figure_positions_finales(cfg, best, f"mc_positions_toutvalide_{et}", f"Tout validé, départ {date}"),
    }
    succes = lambda r: r["fin"] == "arrivee"  # noqa: E731
    from .geo import NM, haversine
    d, a = cfg["mission"]["depart"], cfg["mission"]["arrivee"]
    tot_nm = haversine(d["lat"], d["lon"], a["lat"], a["lon"]) / NM

    def progres(r):
        return max(0.0, 1 - r["dist_restante_nm"] / tot_nm)

    jours_utiles = lambda r: min(r["jours_fin"], 120) / 120.0  # noqa: E731
    g_aj = RM.gains_solutions(cf_aj, succes)
    g_aj_j = RM.gains_solutions(cf_aj, jours_utiles)
    g_aj_p = RM.gains_solutions(cf_aj, progres)
    ref_re = cf_re["reference"]
    g_re = {s: MC.bootstrap_diff(runs, ref_re, succes) for s, runs in cf_re.items() if s != "reference"}
    figs["val_aj"] = RM.figure_valeur_solutions(g_aj, f"valeur_ajout_{et}",
                                                "Gain de P(arrivée) en validant UNE solution (config actuelle)",
                                                "gain de probabilité d'arrivée (points de %) — intervalle à 90 %")
    figs["val_aj_p"] = RM.figure_valeur_solutions(g_aj_p, f"valeur_ajout_progres_{et}",
                                                  "Gain de progression vers l'arrivée en validant UNE solution",
                                                  "gain de fraction de route parcourue avant la fin (points de %)")
    figs["val_re"] = RM.figure_valeur_solutions(g_re, f"valeur_retrait_{et}",
                                                "Perte de P(arrivée) si on RETIRE une solution (tout le reste validé)",
                                                "points de % d'arrivée perdus — intervalle à 90 %")

    # 5. histoire la plus probable
    chrono["figures"], t_etape = time.time() - t_etape, time.time()
    journal("[5/7] Histoire la plus probable (scénario médian)")
    from . import story
    ctx = story.Contexte(chemin_env)
    modal = Counter(r["fin"] for r in base).most_common(1)[0][0]
    cand = sorted([r for r in base if r["fin"] == modal], key=lambda r: r["jours_fin"])
    med = cand[len(cand) // 2]
    rmed = ctx.rejouer(cfg, med["graine"], med["jeu"])
    titre = f"Mission du {date} — histoire la plus probable ({FINS.get(modal, modal)})"
    contexte = (f"Run médian de l'issue la plus fréquente du Monte-Carlo (« {FINS.get(modal, modal)} », "
                f"{100 * len(cand) / len(base):.0f} % des {len(base)} runs).")
    sorties_med = [carte.carte_folium(cfg, rmed, f"histoire_probable_{et}_carte", titre),
                   report.courbes_run(cfg, rmed, f"histoire_probable_{et}_courbes", titre),
                   JB.journal_de_bord(cfg, rmed, f"histoire_probable_{et}_journal", titre, contexte)]
    # même graine, tout validé
    cb = _tout(cfg)
    rbest = ctx.rejouer(cb, med["graine"], med["jeu"])
    titre_b = f"Mission du {date} — même météo, mêmes tirages, toutes solutions validées"
    sorties_best = [carte.carte_folium(cb, rbest, f"histoire_toutvalide_{et}_carte", titre_b),
                    report.courbes_run(cb, rbest, f"histoire_toutvalide_{et}_courbes", titre_b),
                    JB.journal_de_bord(cb, rbest, f"histoire_toutvalide_{et}_journal", titre_b)]

    # 6. récits « et si »
    chrono["histoire"], t_etape = time.time() - t_etape, time.time()
    journal("[6/7] Récits « et si je ne le résous pas ? » (P1–P28)")
    recits = {}
    for pid in ctx.reg["problemes"]:
        f, _ = story.recit_et_si(ctx, cfg, pid, base, dossier=f"histoires_{et}")
        recits[pid] = f

    # 7. chauffage (question B) et rapport
    chrono["recits"], t_etape = time.time() - t_etape, time.time()
    journal("[7/7] Chauffage de la batterie et rédaction du rapport")
    from . import chauffage
    chauffage.analyser(copy.deepcopy(cfg), ctx)
    # piège des derniers milles : sensibilité au centre du cercle d'arrivée (sans pannes, S8 validée)
    from . import run as RR
    import numpy as np
    cercles = []
    lats_c = (51.2, 52.0, 53.0, 54.0)
    cfgs_c = []
    for la in lats_c:
        for k in range(6):
            c = copy.deepcopy(cfg)
            c["mission"]["start"] = RR.iso(RR.t_epoch(cfg["mission"]["start"]) + k * 6 * 3600).replace(" ", "T") + ":00Z"
            c["mission"]["arrivee"]["lat"] = la
            c["solutions"]["S8"] = "validee"
            c["solutions"]["S6"] = "validee"
            cfgs_c.append(c)
    res_c = MC.lancer_physique(cfgs_c, chemin_env)        # 24 missions indépendantes, en parallèle
    for i, la in enumerate(lats_c):
        rs = res_c[6 * i:6 * (i + 1)]
        cercles.append((la, sum(r["fin"] == "arrivee" for r in rs), float(np.median([r["jours"] for r in rs]))))

    chrono["chauffage_cercles"], t_etape = time.time() - t_etape, time.time()
    journal("  durées (s) : " + ", ".join(f"{k} {v:.0f}" for k, v in chrono.items()))
    L = [f"# Epi'Tortue — que se serait-il passé avec un largage le {date} ?", "",
         "> **Avertissement.** Ce rapport rejoue la météo, les vagues, les courants et l'activité de pêche *réels* de "
         "2026 (ERA5, Open-Meteo Marine, Global Fishing Watch). Le bateau, ses pannes et ses rencontres sont "
         "*simulés* avec des taux incertains, calés sur un historique maigre (≈ 30 tentatives Microtransat). "
         "C'est un **scénario plausible et une statistique d'issues, pas une prédiction**. Chaque probabilité est "
         "donnée avec un intervalle à 90 % qui combine l'incertitude sur les paramètres (25 jeux tirés dans les "
         "priors) et le hasard des événements. Toutes les hypothèses chiffrées : `HYPOTHESES.md`.", "",
         f"Configuration : départ {cfg['mission']['depart']['lat']}°N {abs(cfg['mission']['depart']['lon'])}°W "
         f"(≥ 40 nm avant la ligne de départ Ouest), cercle d'arrivée {cfg['mission']['arrivee']['lat']}°N "
         f"{abs(cfg['mission']['arrivee']['lon'])}°W (25 km, ligne Est), orthodromie {tot_nm:.0f} nm ; coque Testa "
         f"(2,35 m, 50 kg, 273 Wc). Solutions en place : "
         + (", ".join(f"{k} = {v}" for k, v in cfg["solutions"].items() if v != "absente") or "aucune") + ".", "",
         "## 1. Réponse courte", ""]
    p_ok = MC.bootstrap(base, succes)
    p_best = MC.bootstrap(best, succes)
    L += [f"- Avec le bateau **tel qu'il est aujourd'hui** (presque toutes les solutions absentes), probabilité "
          f"d'arriver : **{RM.ic(p_ok)}**. Issue la plus fréquente : **{FINS.get(modal, modal)}** "
          f"({100 * len(cand) / len(base):.0f} % des runs), fin médiane au jour "
          f"{sorted(r['jours_fin'] for r in base)[len(base) // 2]:.0f}.",
          f"- Avec **toutes les solutions S1–S20 validées**, même météo : **{RM.ic(p_best)}**.",
          ]
    if res_ete:
        L.append(f"- Même bateau lancé le **{cfg['mission']['comparaison_ete'][:10]}** (fenêtre recommandée par la doc) : "
                 f"actuel {RM.ic(MC.bootstrap(res_ete['actuel'], succes))}, tout validé "
                 f"{RM.ic(MC.bootstrap(res_ete['tout_valide'], succes))}.")
    L += ["", "## 2. Statistique des issues (Monte-Carlo)", "",
          "| Issue | Configuration actuelle | Tout validé |", "|---|---|---|"]
    ia, ib = MC.issues(base), MC.issues(best)
    for k in sorted(set(ia) | set(ib), key=lambda k: -max(ia.get(k, (0,))[0], ib.get(k, (0,))[0])):
        L.append(f"| {FINS.get(k, k)} | {RM.ic(ia[k]) if k in ia else '—'} | {RM.ic(ib[k]) if k in ib else '—'} |")
    L += ["", f"![issues]({_rel(figs['issues'])})", f"![issues tout validé]({_rel(figs['issues_best'])})",
          f"![jours]({_rel(figs['jours'])})", f"![jours]({_rel(figs['jours_best'])})",
          f"![positions]({_rel(figs['pos'])})", f"![positions]({_rel(figs['pos_best'])})", "",
          "## 3. Les tueurs de mission (configuration actuelle)", "",
          "| Problème ayant mis fin à la mission | Probabilité |", "|---|---|"]
    causes = Counter(r["cause_pid"] for r in base if r["fin"] != "arrivee")
    for pid, _ in causes.most_common():
        nomp = ctx.reg["problemes"].get(pid, {}).get("titre", "lenteur (énergie / saison)" if pid == "lenteur" else str(pid))
        L.append(f"| {pid} {nomp} | {RM.ic(MC.bootstrap(base, lambda r, p=pid: r['cause_pid'] == p))} |")
    L += ["", "## 4. Tableau P1–P28 : avec et sans la solution principale", "",
          f"« Avec » = même Monte-Carlo ({n_cf} runs, mêmes graines) où seule la solution principale du problème "
          "passe à « validée ». Intervalles à 90 %.", ""]
    L += RM.tableau_problemes(ctx.reg, cf_aj["reference"], cf_aj)
    L += ["", "## 5. Valeur de chaque solution (pour prioriser)", "",
          "Deux lectures complémentaires, à météo et graines identiques :", "",
          "- **Ajouter une solution** au bateau actuel : quand presque tout manque, une solution seule change "
          "rarement l'arrivée ; la **progression** (fraction de route faite avant la fin) et la **durée de vie** "
          "en mer montrent mieux ce qui retarde la fin.",
          "- **Retirer une solution** d'un bateau où tout est validé : mesure ce dont on ne peut pas se passer.", "",
          "| Solution | + Sx : gain P(arrivée) | + Sx : gain de progression | + Sx : gain de durée (≤ 120 j) | "
          "Tout validé − Sx : perte P(arrivée) |", "|---|---|---|---|---|"]
    for s in sorted(set(g_aj) | set(g_re), key=lambda s: -(g_re.get(s, (0,))[0])):
        a = g_aj.get(s)
        L.append(f"| {s} {RM.NOMS_S.get(s, '')} | {RM.ic(a) if a else '(validée)'} | "
                 f"{RM.ic(g_aj_p[s]) if s in g_aj_p else '—'} | {RM.ic(g_aj_j[s]) if s in g_aj_j else '—'} | "
                 f"{RM.ic(g_re[s]) if s in g_re else '—'} |")
    L += ["", f"![valeur]({_rel(figs['val_re'])})", f"![valeur]({_rel(figs['val_aj_p'])})",
          f"![valeur]({_rel(figs['val_aj'])})", "",
          "## 6. L'histoire la plus probable", "", contexte, "",
          f"- Journal de bord : [{_rel(sorties_med[2])}]({_rel(sorties_med[2])})",
          f"- Carte interactive : [{_rel(sorties_med[0])}]({_rel(sorties_med[0])})",
          f"- Courbes : ![courbes]({_rel(sorties_med[1])})", "",
          f"**Même histoire, toutes solutions validées** : {FINS.get(rbest.fin, rbest.fin)} au jour {rbest.jours:.0f} — "
          f"[journal]({_rel(sorties_best[2])}), [carte]({_rel(sorties_best[0])}).", "",
          "## 7. « Et si je ne le résous pas ? » — un récit par problème", ""]
    for pid, f in recits.items():
        L.append(f"- [{pid} {ctx.reg['problemes'][pid]['titre']}]({_rel(f)})")
    L += ["", "## 8. Chauffer la batterie ? (question B)", "",
          f"Voir [chauffage_{et}.md](chauffage_{et}.md) (coût, gain et verdict par scénario thermique).", "",
          "## 8b. Enseignements physiques (sans pannes, S8 validée)", "",
          "- **Le piège des derniers milles.** Près de l'Irlande, le vent et le courant portent au nord-est. Un bateau "
          "qui arrive un peu tard ou un peu au nord du cercle est entraîné le long du plateau et ne peut pas remonter "
          "au vent avec l'énergie d'hiver : il reste bloqué des semaines. Sensibilité au centre du cercle d'arrivée "
          "(sur la ligne Est, 16°W ; 6 largages décalés de 6 h) :", "",
          "| Centre du cercle | Arrivées | Jour de fin (médiane) |", "|---|---|---|"]
    for la, arr, jm in cercles:
        L.append(f"| {la:.1f}°N 16°W | {arr}/6 | {jm:.0f} |")
    L += ["", "  → l'autopilote vise désormais par défaut le **bord sud du cercle, décalé en amont de la dérive "
          "estimée** (stratégie `navigation.approche.strategie: bord_sud`, H75) ; l'ancienne stratégie (viser le "
          "centre) reste disponible. Effet mesuré : section 11.",
          "- **En hiver, l'électronique mange l'énergie.** La production solaire réelle de janvier (≈ 5 W en "
          "moyenne, ≈ 130 Wh/j) couvre à peine les 114 Wh/j de consommation de bord : il reste quelques watts pour "
          "le moteur. La gestion d'énergie validée (S8) prévoit donc le solaire des 24 h suivantes et ne garde en "
          "réserve que l'énergie de l'électronique de nuit ; quand le soleil manque, elle met le bateau en veille "
          "profonde la nuit (H74). Effet mesuré : section 11.", "",
          "## 9. Contrôle de calibration", "",
          "Toutes solutions « partielles » (≈ flotte historique, hypothèse C1), départ d'été, 200 runs :", ""]
    fam = {"captures (P23/P24)": ("P24", "P23"), "logiciel (P16–P18)": ("P16", "P17", "P18"),
           "mécanique (P4–P8)": ("P4", "P5", "P6", "P7", "P8")}
    for k, pids in fam.items():
        L.append(f"- fin par {k} : {RM.ic(MC.bootstrap(calib, lambda r, p=pids: r['cause_pid'] in p))}")
    L.append(f"- arrivée : {RM.ic(MC.bootstrap(calib, succes))}")
    L += ["- historique cité (≥ 30 tentatives) : captures 9–10 (≈ 32 %), logiciel 8–9 (≈ 28 %), mécanique 3–4 "
          "(≈ 12 %), 1 réussite (≈ 3 %), aucun bateau motorisé arrivé. L'accord n'est qu'indicatif : les "
          "tentatives historiques ont des routes, saisons et durées différentes.", "",
          "## 10. Méthode et limites", "",
          "- Météo ERA5 et vagues/courants Open-Meteo réels, grille "
          + ("1°" if "1deg" in str(chemin_env) else "2°") + ", interpolés le long de la trajectoire ; les extrêmes "
          "locaux (fronts, tourbillons) sont lissés.",
          "- Bateau : bilan de forces 2D (carène Testa, résistance ajoutée par les vagues, fardage, dérive "
          "latérale sans quille) ; énergie solaire réelle (ERA5 direct + diffus, pont plat, IAM) ; batterie "
          "LiFePO4 thermique.",
          "- Navigation : estimateur ensembliste Codac garanti (vérifié par test : la vraie position reste dans la "
          "boîte, hors sauts GPS sous le seuil de détection et pannes de capteur non encore détectées).",
          f"- Monte-Carlo : {n_runs} runs (référence), {n_cf} par contrefactuel, pas de {cfg['simulation']['dt_montecarlo_s'] / 60:.0f} min, "
          "nombres aléatoires communs ; intervalles par bootstrap hiérarchique.",
          "- Le chavirage dépend maintenant de la cambrure des vagues (déferlement) et de la stabilité de la coque "
          "(H71) ; ses seuils « face ou dos à la vague » et les taux sans historique (P1, P3, P10, P11, P13, P14, "
          "P20, P21, P26) restent des jugements : ce sont eux qu'il faut challenger en premier.",
          "- Une seule année de météo (2026) sert au rapport principal ; la section 11 montre ce que change la "
          "météo d'autres années."]
    L += section_corrections(et)
    L += ["", "## 12. Calcul", "",
          f"- Durée totale : {(time.time() - t_debut) / 60:.1f} min ({MC_PROCESSUS(cfg)} processus) ; "
          + ", ".join(f"{k.replace('_', ' ')} {v:.0f} s" for k, v in chrono.items()) + "."]
    L += inclure(f"optimisation_{et}.md", "Optimisations (résultats identiques au bit près)")
    f = OUT / f"rapport_{et}.md"
    f.write_text("\n".join(L), encoding="utf-8")
    journal(f"Rapport : {f}")
    return 0
