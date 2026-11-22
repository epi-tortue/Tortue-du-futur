"""Récits « et si je ne le résous pas ? » et mode histoire interactif.

Toutes les histoires sont rejouées avec la même graine et le même jeu de paramètres :
avec / sans une solution, seule la branche concernée change (nombres aléatoires communs).
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone

from .config import OUT
from .journal import FINS, ISSUES, date_fr, lignes_fin, pos

REPONSES = {"o": "validee", "oui": "validee", "v": "validee", "validee": "validee", "validée": "validee",
            "p": "partielle", "partielle": "partielle", "n": "absente", "non": "absente", "a": "absente",
            "absente": "absente"}


class Contexte:
    """Environnement chargé une fois pour rejouer des runs."""

    def __init__(self, chemin_env=None):
        from . import environment as E
        from . import risks as RK
        self.env = E.Environnement(chemin_env)
        self.cote = E.charger_cote()
        self.reg = RK.charger_registre()
        self.dens = RK.Densites()
        self._jeux = {}

    def jeu(self, cfg, k):
        from . import risks as RK
        cle = (k, cfg["mission"]["depart"]["lat"], cfg["mission"]["depart"]["lon"],
               cfg["mission"]["arrivee"]["lat"], cfg["mission"]["arrivee"]["lon"], RK.signature_registre(cfg))
        if cle not in self._jeux:
            self._jeux[cle] = RK.tirer_parametres(RK.registre_pour(cfg, self.reg), cfg, k, self.dens)
        return self._jeux[cle]

    def rejouer(self, cfg, graine, jeu_k, dt=None):
        from . import run as R
        return R.Simulation(cfg, self.env, self.cote, graine=graine, jeu=self.jeu(cfg, jeu_k), densites=self.dens,
                            registre_yaml=self.reg, dt=dt or cfg["simulation"]["dt_montecarlo_s"]).executer()


# ---------------------------------------------------------------------------
# « Et si je ne le résous pas ? »
# ---------------------------------------------------------------------------
def choisir_run(runs, pid):
    """Run représentatif où `pid` est le premier problème grave ; à défaut, où il survient."""
    cand = [r for r in runs if r["premier_probleme"] == pid]
    if not cand:
        cand = [r for r in runs if r["occurrences"].get(pid, 0) > 0]
    if not cand:
        return None, 0
    cand.sort(key=lambda r: r["jours_fin"])
    return cand[len(cand) // 2], len(cand)


def _recit_depuis(r, t_depuis, n_max_jours=60):
    """Récit compact : chaque jour qui contient un événement, à partir de t_depuis."""
    tr = r.traj
    t0 = tr["t"][0]
    L = []
    jours = sorted({int((e.t - t0) // 86400) for e in r.evenements if e.t >= t_depuis and e.gravite >= 1})
    for k in jours[:n_max_jours]:
        evs = [e for e in r.evenements if t0 + k * 86400 <= e.t < t0 + (k + 1) * 86400 and e.gravite >= 1
               and e.t >= t_depuis]
        if not evs:
            continue
        i = min(range(len(tr["t"])), key=lambda j: abs(tr["t"][j] - evs[0].t))
        L.append(f"- **Jour {k}** ({date_fr(evs[0].t, False)}, {pos(evs[0].lat, evs[0].lon)}, vagues "
                 f"{tr['hs'][i]:.1f} m, vent {tr['vent'][i]:.0f} m/s, batterie {tr['soc_pct'][i]:.0f} %) :")
        for e in evs:
            L.append(f"  - {'⚠️ ' if e.gravite >= 2 else ''}{f'[{e.probleme}] ' if e.probleme else ''}{e.texte}")
    if len(jours) > n_max_jours:
        L.append(f"- … ({len(jours) - n_max_jours} autres jours avec incidents)")
    return L


def recit_et_si(ctx: Contexte, cfg, pid, runs, dossier="histoires"):
    P = ctx.reg["problemes"][pid]
    s = P["solutions"][0]
    rep, n = choisir_run(runs, pid)
    (OUT / dossier).mkdir(parents=True, exist_ok=True)
    f = OUT / dossier / f"{pid}.md"
    L = [f"# {pid} — {P['titre']} : et si je ne le résous pas ?", ""]
    if rep is None:
        L += [f"{pid} n'est survenu dans aucun des {len(runs)} runs du Monte-Carlo (probabilité < {1 / len(runs):.1%} "
              f"sur cette mission). Pas de récit représentatif."]
        f.write_text("\n".join(L), encoding="utf-8")
        return str(f), None
    sans = ctx.rejouer(cfg, rep["graine"], rep["jeu"])
    c_avec = copy.deepcopy(cfg)
    c_avec["solutions"][s] = "validee"
    avec = ctx.rejouer(c_avec, rep["graine"], rep["jeu"])
    t0 = sans.traj["t"][0]
    t_p = sans.premiere.get(pid, t0)
    L += [f"Run représentatif : graine {rep['graine']}, jeu {rep['jeu']} — choisi parmi les {n} runs où {pid} "
          f"survient (en premier si possible), au jour de fin médian. Même météo réelle, mêmes tirages ; seule "
          f"change la solution **{s}** ({cfg['solutions'].get(s)} → validée).", "",
          f"## Sans {s} : la suite de l'histoire", "",
          f"{pid} survient au **jour {(t_p - t0) / 86400:.1f}** ({date_fr(t_p)}).", ""]
    L += _recit_depuis(sans, t_p - 1)
    L += [""] + lignes_fin(sans) + ["", f"## Avec {s} validée (même graine, même météo)", ""]
    if pid in avec.premiere:
        L.append(f"{pid} survient quand même au jour {(avec.premiere[pid] - t0) / 86400:.1f} "
                 f"(la solution réduit la probabilité ou les conséquences, sans les annuler).")
    else:
        L.append(f"{pid} ne survient pas pendant cette mission.")
    L += [""] + _recit_depuis(avec, t_p - 1) + [""] + lignes_fin(avec)
    verdict = ("la solution **sauve la mission**" if avec.succes and not sans.succes else
               "la solution **ne suffit pas** à sauver la mission" if not avec.succes else
               "la mission réussit dans les deux cas")
    L += ["", f"**Verdict sur ce run** : {verdict} (sans : {FINS.get(sans.fin, sans.fin)} au jour {sans.jours:.0f} ; "
          f"avec : {FINS.get(avec.fin, avec.fin)} au jour {avec.jours:.0f}). Un seul run ne prouve rien : voir le "
          f"tableau P1–P28 et la valeur des solutions dans le rapport."]
    f.write_text("\n".join(L), encoding="utf-8")
    return str(f), (sans, avec)


# ---------------------------------------------------------------------------
# Mode histoire interactif
# ---------------------------------------------------------------------------
def _resume_jour(r, k):
    tr = r.traj
    t0 = tr["t"][0]
    sel = [i for i in range(len(tr["t"])) if t0 + k * 86400 <= tr["t"][i] < t0 + (k + 1) * 86400]
    if not sel:
        return None
    i = sel[len(sel) // 2]
    return (f"Jour {k:3d} {date_fr(tr['t'][i], False)}  {pos(tr['lat'][i], tr['lon'][i])}  reste "
            f"{tr['dist_restante_nm'][sel[-1]]:5.0f} nm  vent {max(tr['vent'][j] for j in sel):4.1f} m/s  "
            f"vagues {max(tr['hs'][j] for j in sel):4.1f} m  batterie {tr['soc_pct'][sel[-1]]:3.0f} %  "
            f"[{tr['mode'][sel[-1]]}]")


def mode_histoire(cfg, ctx: Contexte, graine=None, jeu_k=0, reponses=None, entree=input, sortie=print,
                  rapide=False):
    """Avance jour par jour ; s'arrête à chaque incident grave dont la solution n'a pas encore été demandée.

    reponses : {Sx: 'o'|'n'|'partielle'} pour un déroulé scripté (sinon question à l'utilisateur).
    """
    graine = cfg["simulation"]["graine"] if graine is None else graine
    reponses = dict(reponses or {})
    c = copy.deepcopy(cfg)
    demandees = {}
    historique = []                    # (pid, jour, solution, réponse, issue de la branche)
    t_aff = None
    jour_aff = -1
    sortie(f"\n=== Epi'Tortue — largage le {cfg['mission']['start'][:10]} par "
           f"{pos(cfg['mission']['depart']['lat'], cfg['mission']['depart']['lon'])} (graine {graine}) ===")
    sortie("Météo, vagues et courants réels. Chaque incident vous demande si la solution est en place.\n")
    while True:
        r = ctx.rejouer(c, graine, jeu_k)
        t0 = r.traj["t"][0]
        incident = None
        for e in r.evenements:
            if e.gravite < 2 or not e.probleme or (t_aff is not None and e.t <= t_aff):
                continue
            P = ctx.reg["problemes"].get(e.probleme)
            if P is None:
                continue
            s = P["solutions"][0]
            if s in demandees:
                continue
            incident = (e, s)
            break
        t_stop = incident[0].t if incident else r.t_fin_physique
        k_stop = int((t_stop - t0) // 86400)
        if not rapide:
            for k in range(jour_aff + 1, k_stop + 1):
                ligne = _resume_jour(r, k)
                if ligne:
                    sortie(ligne)
        jour_aff = k_stop
        if incident is None:
            break
        e, s = incident
        i = min(range(len(r.traj["t"])), key=lambda j: abs(r.traj["t"][j] - e.t))
        P = ctx.reg["problemes"][e.probleme]
        sortie(f"\n>>> Jour {(e.t - t0) / 86400:.0f}, {pos(e.lat, e.lon)}, vagues {r.traj['hs'][i]:.0f} m : "
               f"{e.texte} ({e.probleme} — {P['titre']}).")
        q = f"    Avez-vous la solution {s} ({_nom_s(s)}) ? [o/n/partielle] "
        if s in reponses:
            rep = reponses[s]
            sortie(q + rep)
        else:
            try:
                rep = entree(q).strip().lower() or "n"
            except EOFError:                      # pas de terminal : réponse par défaut
                rep = "n"
                sortie("n (par défaut)")
        etat = REPONSES.get(rep, "absente")
        demandees[s] = etat
        historique.append((e.probleme, (e.t - t0) / 86400, s, etat))
        if etat != c["solutions"].get(s):
            c["solutions"][s] = etat
            t_aff = e.t - 1
            jour_aff = int((e.t - t0) // 86400) - 1
            sortie(f"    → on rejoue l'histoire avec {s} = {etat} (même météo, mêmes tirages)…\n")
        else:
            t_aff = e.t
    # résumé
    sortie("\n" + "=" * 78)
    sortie(f"FIN : {FINS.get(r.fin, r.fin)} au jour {r.jours:.0f}. Bateau {ISSUES.get(r.issue_physique, r.issue_physique)}"
           f" ({'position connue' if r.retrouve else 'perte silencieuse'}).")
    sortie("Problèmes rencontrés : " + (", ".join(f"{k}×{v}" for k, v in sorted(r.occurrences.items(),
                                                                                  key=lambda x: int(x[0][1:])))
                                      or "aucun"))
    sauves = [h for h in historique if h[3] != "absente" and h[0] not in r.premiere]
    if sauves:
        sortie("Solutions qui ont évité un problème : " + ", ".join(f"{s} ({p})" for p, _, s, _ in sauves))
    sortie("Vos réponses : " + ", ".join(f"{s}={e}" for s, e in demandees.items()))
    sortie(f"Rejouer la même histoire : python main.py histoire --start {cfg['mission']['start'][:10]} "
           f"--graine {graine} --reponses \"{','.join(f'{s}={e[0]}' for s, e in demandees.items())}\"")
    return r, demandees


def _nom_s(s):
    from .rapport_mc import NOMS_S
    return NOMS_S.get(s, s)
