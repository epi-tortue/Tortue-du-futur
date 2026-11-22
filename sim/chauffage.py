"""Question B : chauffer la batterie (B2) contre batterie à SST + Δ (B1) — coût et gain."""
from __future__ import annotations

import copy

from .config import OUT


def analyser(cfg, ctx, journal=print):
    from . import run as R
    et = cfg["mission"]["start"][:10].replace("-", "")
    L = ["# Chauffer la batterie : combien ça coûte, combien ça rapporte ?", "",
         f"Départ {cfg['mission']['start'][:10]}. Navigation parfaite, sans pannes (on isole l'effet thermique). "
         "Chaque ligne = moyenne sur un ensemble de largages décalés de 6 h (la trajectoire est chaotique : quelques "
         "Wh de différence font attraper ou rater une fenêtre météo). "
         "Gestion d'énergie S8 validée et S6 en place (verrou de charge < 0 °C). La batterie suit l'eau de mer "
         "(T_bat → SST + Δ) avec une constante de temps de ~2,8 h ; le chauffage (10 W max, consigne 6 °C) "
         "n'utilise que le surplus solaire (mode « quand_soleil ») ou tourne en permanence (« toujours »).", "",
         "| Δ = T_bat − SST | Chauffage | Énergie chauffage | Énergie bloquée par le froid | Énergie écrêtée | "
         "Solaire utilisé | Moteur | Arrivées | Jour de fin (médiane) | Reste (nm, médiane) |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    from .run import iso, t_epoch
    n_ens = cfg.get("analyses", {}).get("chauffage_ensemble", 8)
    t_ref = t_epoch(cfg["mission"]["start"])
    bilan = {}
    scenarios = [(delta, mode) for delta in (2.0, 0.0, -3.0, -6.0) for mode in (None, "quand_soleil", "toujours")]
    cfgs = []
    for delta, mode in scenarios:
        for k in range(n_ens):               # ensemble de largages décalés de 6 h (effet chaotique de la météo)
            c = copy.deepcopy(cfg)
            c["mission"]["start"] = iso(t_ref + k * 6 * 3600).replace(" ", "T") + ":00Z"
            c["solutions"]["S8"] = "validee"
            c["solutions"]["S6"] = "validee"
            c["bateau"]["batterie"]["delta_t_sur_mer_c"] = delta
            c["bateau"]["batterie"]["chauffage"]["active"] = mode is not None
            if mode:
                c["bateau"]["batterie"]["chauffage"]["mode"] = mode
            cfgs.append(c)
    # les 96 missions sont indépendantes : en parallèle (mêmes résultats que l'une après l'autre)
    from . import montecarlo as MC
    resultats = MC.lancer_physique(cfgs, ctx.env.chemin)
    import numpy as np
    for i, (delta, mode) in enumerate(scenarios):
        agg = dict(ch=0.0, bloq=0.0, ecr=0.0, sol=0.0, mot=0.0, arr=0, jours=[], reste=[])
        for r in resultats[i * n_ens:(i + 1) * n_ens]:
            st = r["stats"]
            agg["ch"] += st["e_chauffage"] / n_ens
            agg["bloq"] += st["e_froid_bloquee"] / n_ens
            agg["ecr"] += st["e_ecretee"] / n_ens
            agg["sol"] += (st["e_solaire"] - st["e_ecretee"]) / n_ens
            agg["mot"] += st["e_moteur"] / n_ens
            agg["arr"] += r["fin"] == "arrivee"
            agg["jours"].append(r["jours"])
            agg["reste"].append(r["reste_nm"])
        L.append(f"| {delta:+.0f} °C | {mode or 'non'} | {agg['ch']:.0f} Wh | {agg['bloq']:.0f} Wh | "
                 f"{agg['ecr']:.0f} Wh | {agg['sol']:.0f} Wh | {agg['mot']:.0f} Wh | {agg['arr']}/{n_ens} | "
                 f"{np.median(agg['jours']):.0f} | {np.median(agg['reste']):.0f} |")
        journal(L[-1])
        bilan[(delta, mode)] = (agg["ch"], agg["bloq"], float(np.median(agg["jours"])), agg["arr"])
    L += ["", "## Verdict", ""]
    for delta in (2.0, 0.0, -3.0, -6.0):
        ch0, bl0, j0, a0 = bilan[(delta, None)]
        ch1, bl1, j1, a1 = bilan[(delta, "quand_soleil")]
        recup = bl0 - bl1
        L.append(f"- **Δ = {delta:+.0f} °C** : sans chauffage, {bl0:.0f} Wh refusés par le froid. Avec chauffage "
                 f"« quand_soleil » : {ch1:.0f} Wh dépensés, {recup:.0f} Wh récupérés → bilan {recup - ch1:+.0f} Wh ; "
                 f"jour d'arrivée médian {j0:.0f} → {j1:.0f} ({a0} → {a1} arrivées sur {n_ens}).")
    L += ["", "Le surplus solaire de l'hiver est faible : avec la batterie couplée à l'eau (Δ ≥ 0), le froid ne "
          "bloque presque rien et le chauffage est une dépense pure. Il ne devient rentable que si la batterie est "
          "nettement plus froide que l'eau (Δ ≤ −3 °C), cas d'un compartiment couplé à l'air. Attention : l'issue "
          "est très sensible au calendrier d'arrivée (voir « piège des 100 derniers milles » dans le rapport) — un "
          "écart de jours peut venir d'une fenêtre météo attrapée ou manquée, pas de l'énergie elle-même.", ""]
    L += ["", "Lecture : « énergie bloquée par le froid » = surplus solaire que le BMS refuse parce que la batterie "
          "est sous 5 °C (charge limitée à 0,1 C) ou sous 0 °C (charge interdite). Le chauffage n'a d'intérêt que si ce "
          "volume dépasse sa propre consommation. Δ = +2 °C est l'hypothèse par défaut (batterie au fond de coque, "
          "couplée à l'eau) ; Δ négatifs = batterie plus froide que l'eau (couplage à l'air, nuit, vent)."]
    f = OUT / f"chauffage_{et}.md"
    f.write_text("\n".join(L), encoding="utf-8")
    journal(f"→ {f}")
    return str(f)


