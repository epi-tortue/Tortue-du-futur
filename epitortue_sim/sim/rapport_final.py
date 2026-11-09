"""Rapport final : Monte-Carlo, contrefactuels, tableau P1–P28, histoire la plus probable,
récits « et si », comparaison de saison, chauffage. Écrit out/rapport_<date>.md."""
from __future__ import annotations

import copy
import time
from collections import Counter

from . import montecarlo as MC
from . import rapport_mc as RM
from .config import OUT
from .journal import FINS


def _tout(cfg, etat="validee"):
    c = copy.deepcopy(cfg)
    for s in c["solutions"]:
        c["solutions"][s] = etat
    return c


def _rel(f):
    return str(f).replace(str(OUT) + "\\", "").replace(str(OUT) + "/", "").replace("\\", "/")


def generer(cfg, n_runs, n_cf, chemin_env, ete=True, journal=print):
    t_debut = time.time()
    et = cfg["mission"]["start"][:10].replace("-", "")
    date = cfg["mission"]["start"][:10]
    OUT.mkdir(exist_ok=True)
    R = {}

    # 1. Monte-Carlo de référence + « tout validé »
    journal(f"[1/7] Monte-Carlo : configuration actuelle et « tout validé » ({n_runs} runs chacun)")
    res = MC.lancer({"actuel": cfg, "tout_valide": _tout(cfg)}, n_runs, chemin_env, journal=journal)
    MC.sauver(res, f"reference_{et}")
    base, best = res["actuel"], res["tout_valide"]

    # 2. contrefactuels
    journal(f"[2/7] Contrefactuels « + Sx » et « tout validé − Sx » ({n_cf} runs par configuration)")
    cf_aj = MC.lancer(MC.configs_contrefactuelles(cfg, "ajout"), n_cf, chemin_env, journal=journal)
    MC.sauver(cf_aj, f"cf_ajout_{et}")
    cf_re = MC.lancer(MC.configs_contrefactuelles(cfg, "retrait"), n_cf, chemin_env, journal=journal)
    MC.sauver(cf_re, f"cf_retrait_{et}")

    # 3. saison + calibration
    res_ete = None
    if ete:
        journal("[3/7] Comparaison : départ le " + cfg["mission"]["comparaison_ete"][:10])
        ce = copy.deepcopy(cfg)
        ce["mission"]["start"] = cfg["mission"]["comparaison_ete"]
        res_ete = MC.lancer({"actuel": ce, "tout_valide": _tout(ce)}, max(100, n_runs // 2), chemin_env,
                            journal=journal)
        MC.sauver(res_ete, f"ete_{ce['mission']['start'][:10].replace('-', '')}")
    journal("[3b/7] Contrôle de calibration (toutes solutions « partielles », départ d'été)")
    ch = _tout(cfg, "partielle")
    ch["mission"]["start"] = cfg["mission"]["comparaison_ete"]
    calib = MC.lancer({"historique": ch}, 200, chemin_env, journal=journal)["historique"]

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
    journal("[5/7] Histoire la plus probable (scénario médian)")
    from . import carte, journal as JB, report, story
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
    journal("[6/7] Récits « et si je ne le résous pas ? » (P1–P28)")
    recits = {}
    for pid in ctx.reg["problemes"]:
        f, _ = story.recit_et_si(ctx, cfg, pid, base, dossier=f"histoires_{et}")
        recits[pid] = f

    # 7. chauffage (question B) et rapport
    journal("[7/7] Chauffage de la batterie et rédaction du rapport")
    from . import chauffage
    chauffage.analyser(copy.deepcopy(cfg), ctx)
    # piège des derniers milles : sensibilité au centre du cercle d'arrivée (sans pannes, S8 validée)
    from . import run as RR
    import numpy as np
    cercles = []
    for la in (51.2, 52.0, 53.0, 54.0):
        jours, arr = [], 0
        for k in range(6):
            c = copy.deepcopy(cfg)
            c["mission"]["start"] = RR.iso(RR.t_epoch(cfg["mission"]["start"]) + k * 6 * 3600).replace(" ", "T") + ":00Z"
            c["mission"]["arrivee"]["lat"] = la
            c["solutions"]["S8"] = "validee"
            c["solutions"]["S6"] = "validee"
            r = RR.Simulation(c, ctx.env, ctx.cote, dt=c["simulation"]["dt_montecarlo_s"],
                              modules=dict(estimateur=False, risques=False)).executer()
            jours.append(r.jours)
            arr += r.fin == "arrivee"
        cercles.append((la, arr, float(np.median(jours))))

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
    L += ["", "  → viser le **sud du segment** et aborder par le sud-ouest (au vent) est une piste S19 à tester "
          "(paramètre `mission.arrivee` de config.yaml).",
          "- **En hiver, l'électronique mange l'énergie.** La production solaire réelle de janvier (≈ 5 W en "
          "moyenne, ≈ 130 Wh/j) couvre à peine les 114 Wh/j de consommation de bord : il reste quelques watts pour "
          "le moteur. La veille de nuit (option `energie.validee.veille_nuit`) économise de l'énergie mais retarde "
          "l'arrivée dans la zone critique ; elle est désactivée par défaut.", "",
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
          "- Le modèle de chavirage (×(Hs/4)⁴ au-delà de 3 m) et les taux sans historique (P1, P3, P10, P11, P13, "
          "P14, P20, P21, P26) sont des jugements : ce sont eux qu'il faut challenger en premier.",
          f"- Calcul : {(time.time() - t_debut) / 60:.0f} min."]
    f = OUT / f"rapport_{et}.md"
    f.write_text("\n".join(L), encoding="utf-8")
    journal(f"Rapport : {f}")
    return 0
