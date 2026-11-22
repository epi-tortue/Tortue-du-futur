"""Journal de bord en français (Markdown), jour par jour."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .config import OUT

MODES = {"normal": "route vers l'arrivée", "degrade": "mode dégradé (cap fixe ENE, puissance réduite)",
         "sans_cap": "attente (aucun cap fiable, moteur coupé)", "black-out": "black-out (batterie vide)",
         "veille": "veille de nuit planifiée (économie d'énergie)",
         "gel": "calculateur figé", "bug_cap": "cap erroné (bug logiciel)",
         "bug_moteur": "moteur bloqué à l'arrêt (bug logiciel)",
         "failsafe_retour": "failsafe « retour au point de départ »", "epave": "épave (dérive libre)"}

FINS = {
    "arrivee": "arrivée dans le cercle — traversée réussie",
    "capture": "récupéré par un pêcheur / un navire",
    "perdu_filet": "perdu, entraîné par un engin de pêche",
    "coule": "coulé",
    "echouement": "échoué à la côte avant la ligne",
    "chavire": "resté chaviré",
    "panne_energie": "panne d'énergie définitive",
    "sans_propulsion": "plus de propulsion",
    "sans_gouverne": "plus de gouverne",
    "calculateur": "calculateur figé",
    "disqualification": "disqualifié pour silence radio (règle B1)",
    "logiciel": "logiciel bloqué (cap erroné ou moteur arrêté)",
    "failsafe": "failsafe « retour au départ »",
    "navigation": "GPS hors service : arrivée impossible à prouver",
    "fin_donnees": "toujours en mer à la fin des données météo (trop lent)",
    "hors_domaine": "sorti de la zone simulée sans avoir atteint le cercle",
}

ISSUES = {"arrivee": "arrivé", "capture": "à bord d'un navire de pêche", "perdu_filet": "perdu dans un engin de pêche",
          "coule": "par le fond", "echouement": "échoué à la côte", "en_mer": "en mer, en état de marche",
          "derive": "à la dérive", "hors_domaine": "sorti de la zone simulée"}


def pos(la, lo):
    return f"{abs(la):.2f}°{'N' if la >= 0 else 'S'} {abs(lo):.2f}°{'W' if lo < 0 else 'E'}"


def date_fr(t, heure=True):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%d/%m/%Y %H:%M" if heure else "%d/%m/%Y")


def lignes_jour(r, k, mode_prec=None):
    """Lignes Markdown du jour k (0 = jour du largage) et dernier mode."""
    tr = r.traj
    t0 = tr["t"][0]
    a, b = t0 + k * 86400, t0 + (k + 1) * 86400
    sel = (tr["t"] >= a) & (tr["t"] < b)
    if not sel.any():
        return [], mode_prec
    i_mid = int(np.argmin(np.abs(tr["t"] - (a + 43200))))
    ip = np.where(tr["t"] < a)[0]
    d_debut = tr["dist_restante_nm"][ip[-1]] if len(ip) else tr["dist_restante_nm"][0]
    d_fin = tr["dist_restante_nm"][sel][-1]
    gain = d_debut - d_fin
    dt = np.diff(tr["t"], prepend=tr["t"][0])[sel] / 3600.0
    e_sol = float((tr["p_solaire"][sel] * dt).sum())
    e_mot = float((tr["p_moteur"][sel] * dt).sum())
    e_ch = float((tr["p_chauffage"][sel] * dt).sum())
    modes = list(dict.fromkeys(tr["mode"][sel]))
    L = [f"## Jour {k} — {date_fr(a, False)}",
         f"- **Position** (midi) : {pos(tr['lat'][i_mid], tr['lon'][i_mid])} — reste {d_fin:.0f} nm "
         f"({'gagné' if gain >= 0 else 'perdu'} {abs(gain):.0f} nm dans la journée)",
         f"- **Météo** : vent moyen {tr['vent'][sel].mean():.0f} m/s (rafales {tr['rafales'][sel].max():.0f}), "
         f"vagues jusqu'à {tr['hs'][sel].max():.1f} m, courant {tr['courant'][sel].mean():.2f} m/s, "
         f"eau {tr['sst'][sel].mean():.1f} °C, air {tr['t_air'][sel].min():.0f} à {tr['t_air'][sel].max():.0f} °C",
         f"- **Énergie** : solaire {e_sol:.0f} Wh, moteur {e_mot:.0f} Wh"
         + (f", chauffage {e_ch:.0f} Wh" if e_ch > 0.5 else "")
         + f" ; batterie {tr['soc_pct'][sel].min():.0f}–{tr['soc_pct'][sel].max():.0f} % à {tr['t_bat'][sel].mean():.1f} °C",
         f"- **Navigation** : GPS disponible {100 * tr['gps'][sel].mean():.0f} % du temps ; boîte Codac jusqu'à "
         f"{tr['boite_km'][sel].max():.1f} km ; vitesse fond moyenne {tr['v_fond'][sel].mean():.2f} m/s"]
    if modes and modes != [mode_prec]:
        L.append("- **Autopilote** : " + " → ".join(MODES.get(m, m) for m in modes))
    for e in [e for e in r.evenements if a <= e.t < b and e.gravite >= 1]:
        tag = f"**[{e.probleme}]** " if e.probleme else ""
        L.append(f"- {'⚠️ ' if e.gravite >= 2 else ''}{datetime.fromtimestamp(e.t, timezone.utc).strftime('%H:%M')} "
                 f"{tag}{e.texte} ({pos(e.lat, e.lon)})")
    return L, (modes[-1] if modes else mode_prec)


def lignes_fin(r):
    tr = r.traj
    st = r.stats
    cause = f" (cause : {st.get('cause_pid')})" if st.get("cause_pid") else ""
    chauffe = f", chauffage {st['e_chauffage'] / 1000:.2f} kWh" if st["e_chauffage"] > 1 else ""
    L = ["## Fin de l'histoire", "",
         f"- **Fin de mission** : {FINS.get(r.fin, r.fin)}, jour {r.jours:.1f} ({date_fr(r.t_fin)}){cause}",
         f"- **Devenir du bateau** : {ISSUES.get(r.issue_physique, r.issue_physique or '—')} ; dernière position "
         f"{pos(tr['lat'][-1], tr['lon'][-1])} le {date_fr(r.t_fin_physique)} ; "
         + ("position connue (télémétrie, balise ou récupération)" if r.retrouve else
            "**perte silencieuse** : personne ne sait où il est"),
         f"- **Bilan** : {st['dist_parcourue_nm']:.0f} nm parcourus ; solaire {st['e_solaire'] / 1000:.1f} kWh, "
         f"moteur {st['e_moteur'] / 1000:.1f} kWh, électronique {st['e_hotel'] / 1000:.1f} kWh{chauffe} ; "
         f"{st['blackouts']} black-out(s), {st['redemarrages']} redémarrage(s) ; "
         f"{st['fix_rejetes']} fix GPS rejetés pour {st['sauts_gps']} sauts injectés"]
    if r.occurrences:
        L.append("- **Problèmes rencontrés** : " + ", ".join(
            f"{k}×{v}" for k, v in sorted(r.occurrences.items(), key=lambda x: int(x[0][1:]))))
    return L


def journal_de_bord(cfg: dict, r, nom: str, titre: str, contexte: str = "") -> str:
    tr = r.traj
    t0 = tr["t"][0]
    sol = ", ".join(f"{k}={v}" for k, v in r.solutions.items() if v != "absente") or "aucune"
    L = [f"# {titre}", ""]
    if contexte:
        L += [contexte, ""]
    L += [f"*Largage le {date_fr(t0)} UTC par {pos(tr['lat'][0], tr['lon'][0])}. Solutions en place : {sol}. "
          f"Graine {r.graine}, jeu de paramètres {r.jeu}.*", "",
          "> Scénario plausible rejoué sur la météo réelle 2026, **pas une prédiction** : pannes et rencontres "
          "sont tirées au hasard selon des taux incertains (voir HYPOTHESES.md).", ""]
    mode = None
    for k in range(int((tr["t"][-1] - t0) // 86400) + 1):
        lj, mode = lignes_jour(r, k, mode)
        if lj:
            L += lj + [""]
    L += lignes_fin(r)
    OUT.mkdir(exist_ok=True)
    f = OUT / f"{nom}.md"
    f.write_text("\n".join(L), encoding="utf-8")
    return str(f)
