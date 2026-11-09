"""Simulateur de mission Epi'Tortue — point d'entrée.

  python main.py --start 2026-01-01 --runs 500        rapport complet (= commande « rapport »)
  python main.py donnees [--fine]                      télécharge et met en cache (reprenable)
  python main.py etat                                  état du cache
  python main.py controle [--date ...]                 figure de contrôle vent + vagues + pêche
  python main.py simuler [--graine N] [--physique]     une mission détaillée (carte, courbes, journal)
  python main.py chauffage                             question B : chauffer la batterie, ça rapporte ?
  python main.py montecarlo [--runs N]                 statistique des issues
  python main.py contrefactuels [--runs N]             valeur de chaque solution S1–S20
  python main.py calibration [--runs N]                contrôle : scénario « historique » (tout partiel)
  python main.py histoire [--graine N] [--reponses "S5=o,S8=n"]   mode histoire interactif
  python main.py rapport [--runs N] [--sans-ete]       tout : MC, contrefactuels, P1–P28, récits, été
  python main.py recits                                régénère récits et histoire probable (MC sauvegardé)
Options communes : --start AAAA-MM-JJ, --config fichier.yaml
"""
from __future__ import annotations

import argparse
import copy
import sys
import warnings

warnings.filterwarnings("ignore")

from sim import config as C  # noqa: E402
from sim.config import DATA, OUT  # noqa: E402


def chemin_grille():
    for nom in ("grille_1deg.npz", "grille_2deg.npz"):
        if (DATA / nom).exists():
            return DATA / nom
    if (DATA / "grille_2deg_partiel.npz").exists():
        print("ATTENTION : grille partielle (téléchargement incomplet) — résultats limités dans le temps.")
        return DATA / "grille_2deg_partiel.npz"
    raise SystemExit("Aucune grille de données : lancer d'abord « python main.py donnees ».")


def appliquer_start(cfg, start):
    if start:
        cfg["mission"]["start"] = start if "T" in start else f"{start}T12:00:00Z"
    return cfg


def etiquette(cfg):
    return cfg["mission"]["start"][:10].replace("-", "")


# ---------------------------------------------------------------------------
def cmd_donnees(args, cfg):
    from sim import environment as E

    print(f"Fin des données ERA5 : {E.fin_donnees(cfg)}")
    E.telecharger_cote(cfg)
    if not args.sans_gfw:
        E.telecharger_gfw(cfg)
    grilles = [cfg["donnees"]["grille"]]
    if args.fine and cfg["donnees"]["grille_fine"]["active"]:
        grilles.append(cfg["donnees"]["grille_fine"])
    for g in grilles:
        try:
            E.telecharger_open_meteo(cfg, g)
        except E.QuotaJournalierAtteint as e:
            print(f"Quota journalier Open-Meteo atteint : relancer demain (reprise automatique). {e}")
            return 2
        print(f"Grille assemblée : {E.assembler(cfg, g)}")
    return 0


def cmd_etat(args, cfg):
    from sim import environment as E

    for nom in ("grille", "grille_fine"):
        res = E.etat_cache(cfg, cfg["donnees"][nom])
        fait = sum(n for n, _ in res.values())
        tot = sum(t for _, t in res.values())
        print(f"== {nom} : {fait}/{tot} fichiers point×mois ==")
        for k, (n, t) in res.items():
            if n < t:
                print(f"  {k}: {n}/{t}")
    return 0


def cmd_controle(args, cfg):
    from sim import report
    print(f"Figure : {report.figure_controle(cfg, args.date)}")
    return 0


def _sorties_run(cfg, r, nom, titre, contexte=""):
    from sim import carte, journal, report
    out = [carte.carte_folium(cfg, r, f"{nom}_carte", titre),
           report.courbes_run(cfg, r, f"{nom}_courbes", titre),
           report.carte_trajectoires(cfg, {"trajectoire": r}, f"{nom}_carte_statique", titre),
           journal.journal_de_bord(cfg, r, f"{nom}_journal", titre, contexte)]
    return out


def cmd_simuler(args, cfg):
    from sim import story
    ctx = story.Contexte(chemin_grille())
    if args.physique:
        from sim import run as R
        r = R.Simulation(cfg, ctx.env, ctx.cote, modules=dict(energie=False, estimateur=False, risques=False)).executer()
    else:
        r = ctx.rejouer(cfg, args.graine if args.graine is not None else cfg["simulation"]["graine"], args.jeu,
                        dt=cfg["simulation"]["dt_dynamique_s"] if args.fin else None)
    print(f"Fin : {r.fin} au jour {r.jours:.1f} ; devenir : {r.issue_physique}")
    for f in _sorties_run(cfg, r, f"mission_{etiquette(cfg)}_g{r.graine}", f"Mission du {cfg['mission']['start'][:10]}"):
        print("  ", f)
    return 0


def cmd_chauffage(args, cfg):
    from sim import chauffage, story
    chauffage.analyser(cfg, story.Contexte(chemin_grille()))
    return 0


def cmd_montecarlo(args, cfg):
    from sim import montecarlo as MC
    from sim import rapport_mc as RM
    n = args.runs or cfg["simulation"]["n_runs"]
    res = MC.lancer({"reference": cfg}, n, chemin_grille())
    runs = res["reference"]
    MC.sauver(res, f"reference_{etiquette(cfg)}")
    et = etiquette(cfg)
    print(RM.figure_issues(runs, f"mc_issues_{et}", f"Issues de la mission ({len(runs)} runs, départ {cfg['mission']['start'][:10]})"))
    print(RM.figure_jours(runs, f"mc_jours_{et}", "Jour de fin de mission"))
    print(RM.figure_positions_finales(cfg, runs, f"mc_positions_{et}", f"Départ {cfg['mission']['start'][:10]}"))
    for k, v in MC.issues(runs).items():
        print(f"  {k:18s} {RM.ic(v)}")
    return 0


def cmd_contrefactuels(args, cfg):
    from sim import montecarlo as MC
    n = args.runs or cfg["simulation"]["n_runs_contrefactuel"]
    for mode in ("ajout", "retrait"):
        res = MC.lancer(MC.configs_contrefactuelles(cfg, mode), n, chemin_grille())
        MC.sauver(res, f"cf_{mode}_{etiquette(cfg)}")
    return 0


def cmd_calibration(args, cfg):
    """Contrôle : tout « partiel » (≈ flotte historique, choix C1), départ été."""
    from sim import montecarlo as MC
    from sim import rapport_mc as RM
    c = copy.deepcopy(cfg)
    for s in c["solutions"]:
        c["solutions"][s] = "partielle"
    appliquer_start(c, args.start or "2026-06-15")
    res = MC.lancer({"historique": c}, args.runs or 200, chemin_grille())
    runs = res["historique"]
    fam = {"captures (P23/P24)": ("P24", "P23"), "logiciel (P16–P18)": ("P16", "P17", "P18"),
           "mécanique (P4–P8)": ("P4", "P5", "P6", "P7", "P8")}
    print("Scénario « historique » (toutes solutions partielles) — fin de mission par famille :")
    for k, pids in fam.items():
        print(f"  {k:22s} {RM.ic(MC.bootstrap(runs, lambda r, p=pids: r['cause_pid'] in p))}")
    print(f"  {'arrivée':22s} {RM.ic(MC.bootstrap(runs, lambda r: r['fin'] == 'arrivee'))}")
    print("Historique Microtransat (≥ 30 tentatives) : captures 9–10, logiciel 8–9, mécanique 3–4, 1 réussite.")
    MC.sauver(res, f"calibration_{etiquette(c)}")
    return 0


def cmd_histoire(args, cfg):
    from sim import story
    ctx = story.Contexte(chemin_grille())
    rep = {}
    if args.reponses:
        for x in args.reponses.split(","):
            if "=" in x:
                k, v = x.split("=")
                rep[k.strip().upper()] = v.strip().lower()
    story.mode_histoire(cfg, ctx, graine=args.graine, jeu_k=args.jeu, reponses=rep, rapide=args.rapide)
    return 0


def cmd_recits(args, cfg):
    """Régénère les récits « et si » et l'histoire la plus probable depuis le Monte-Carlo sauvegardé."""
    from collections import Counter

    from sim import carte, journal, montecarlo as MC, report, story
    from sim.journal import FINS
    et = etiquette(cfg)
    base = MC.charger(f"reference_{et}")["actuel"]
    ctx = story.Contexte(chemin_grille())
    modal = Counter(r["fin"] for r in base).most_common(1)[0][0]
    cand = sorted([r for r in base if r["fin"] == modal], key=lambda r: r["jours_fin"])
    med = cand[len(cand) // 2]
    r = ctx.rejouer(cfg, med["graine"], med["jeu"])
    titre = f"Mission du {cfg['mission']['start'][:10]} — histoire la plus probable ({FINS.get(modal, modal)})"
    ctxt = (f"Run médian de l'issue la plus fréquente du Monte-Carlo (« {FINS.get(modal, modal)} », "
            f"{100 * len(cand) / len(base):.0f} % des {len(base)} runs).")
    print(carte.carte_folium(cfg, r, f"histoire_probable_{et}_carte", titre))
    print(report.courbes_run(cfg, r, f"histoire_probable_{et}_courbes", titre))
    print(journal.journal_de_bord(cfg, r, f"histoire_probable_{et}_journal", titre, ctxt))
    for pid in ctx.reg["problemes"]:
        print(story.recit_et_si(ctx, cfg, pid, base, dossier=f"histoires_{et}")[0])
    return 0


def cmd_rapport(args, cfg):
    from sim import rapport_final
    return rapport_final.generer(cfg, args.runs or cfg["simulation"]["n_runs"],
                                 args.runs_cf or cfg["simulation"]["n_runs_contrefactuel"], chemin_grille(),
                                 ete=not args.sans_ete)


# ---------------------------------------------------------------------------
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    commandes = {"donnees", "etat", "controle", "simuler", "chauffage", "montecarlo", "contrefactuels",
                 "calibration", "histoire", "rapport", "recits"}
    if not any(a in commandes for a in argv):
        argv = ["rapport"] + argv
    p = argparse.ArgumentParser(description="Simulateur de mission Epi'Tortue")
    p.add_argument("--config", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    def commun(sp):
        sp.add_argument("--start", default=None, help="date de largage AAAA-MM-JJ (12:00 UTC)")
        sp.add_argument("--runs", type=int, default=None)
        sp.add_argument("--graine", type=int, default=None)
        sp.add_argument("--jeu", type=int, default=0, help="indice du jeu de paramètres")
        sp.add_argument("--config", dest="config_sous", default=None, help="autre fichier de configuration")
        return sp

    d = commun(sub.add_parser("donnees"))
    d.add_argument("--fine", action="store_true")
    d.add_argument("--sans-gfw", action="store_true")
    commun(sub.add_parser("etat"))
    c = commun(sub.add_parser("controle"))
    c.add_argument("--date", default="2026-01-01T12:00")
    s = commun(sub.add_parser("simuler"))
    s.add_argument("--physique", action="store_true", help="bateau seul, GPS parfait, sans énergie ni pannes")
    s.add_argument("--fin", action="store_true", help="pas de temps fin (10 min) au lieu du pas Monte-Carlo")
    for nom in ("chauffage", "montecarlo", "contrefactuels", "calibration", "recits"):
        commun(sub.add_parser(nom))
    h = commun(sub.add_parser("histoire"))
    h.add_argument("--reponses", default=None, help='ex. "S5=o,S8=partielle,S11=n"')
    h.add_argument("--rapide", action="store_true", help="n'affiche que les incidents")
    r = commun(sub.add_parser("rapport"))
    r.add_argument("--runs-cf", type=int, default=None)
    r.add_argument("--sans-ete", action="store_true")
    args = p.parse_args(argv)
    cfg = appliquer_start(C.charger(getattr(args, "config_sous", None) or args.config), getattr(args, "start", None))
    fn = {"donnees": cmd_donnees, "etat": cmd_etat, "controle": cmd_controle, "simuler": cmd_simuler,
          "chauffage": cmd_chauffage, "montecarlo": cmd_montecarlo, "contrefactuels": cmd_contrefactuels,
          "calibration": cmd_calibration, "histoire": cmd_histoire, "rapport": cmd_rapport,
          "recits": cmd_recits}[args.cmd]
    return fn(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
