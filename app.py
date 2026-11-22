"""Interface graphique du simulateur Epi'Tortue :  streamlit run app.py

L'interface ne calcule rien elle-même : elle édite des copies de config.yaml, lance `main.py` en
arrière-plan (sim/taches.py : non bloquant, annulable) et affiche ce que sim/ produit dans out/.
`python main.py ...` fonctionne exactement de la même façon sans elle.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import shutil
import sys
import time
from pathlib import Path

import streamlit as st
import yaml

if __name__ == "__main__":
    from streamlit import runtime

    if not runtime.exists():
        # Lancé par `python app.py` : sans serveur Streamlit, chaque st.* ne ferait qu'avertir
        # « missing ScriptRunContext ». On relance la bonne commande à la place.
        import subprocess

        sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", __file__, *sys.argv[1:]]))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sim import config as C  # noqa: E402
from sim import taches as T  # noqa: E402
from sim.config import DATA, OUT, RACINE  # noqa: E402

CONFIGS = RACINE / "configs"
ORIGINAL = RACINE / "config.yaml"
ETATS = ["absente", "partielle", "validee"]
LIB_ETATS = {"absente": "absente", "partielle": "partielle", "validee": "validée"}

st.set_page_config(page_title="Epi'Tortue — simulateur de mission", page_icon="🐢", layout="wide")


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def fichiers_config() -> dict:
    """{nom affiché: chemin} : l'original, puis les copies de configs/."""
    out = {"config.yaml (original)": ORIGINAL}
    if CONFIGS.exists():
        for f in sorted(CONFIGS.glob("*.yaml")):
            out[f"configs/{f.name}"] = f
    return out


def choisir_config(cle: str, aide: str = "") -> Path:
    fc = fichiers_config()
    defaut = st.session_state.get("config_courante")
    noms = list(fc)
    i = noms.index(defaut) if defaut in noms else 0
    nom = st.selectbox("Configuration", noms, index=i, key=cle, help=aide or None)
    return fc[nom]


def noms_solutions() -> dict:
    from sim.rapport_mc import NOMS_S
    return NOMS_S


@st.cache_resource(show_spinner="Chargement de la météo et du trait de côte…")
def contexte(chemin_grille: str):
    from sim import story
    return story.Contexte(Path(chemin_grille))


def grille_pour(cfg) -> Path:
    from sim import environment as E
    f = E.chemin_grille(cfg, strict=False)
    if f is None:
        st.error("Aucune grille météo en cache : voir l'onglet « Données ».")
        st.stop()
    return f


@st.cache_data(show_spinner=False)
def _json(chemin: str, mtime: float):
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def charger_json(f: Path):
    return _json(str(f), f.stat().st_mtime)


@st.cache_data(show_spinner="Intervalles à 90 % (bootstrap)…")
def _issues(chemin: str, mtime: float, cle: str):
    from sim import montecarlo as MC
    runs = json.loads(Path(chemin).read_text(encoding="utf-8"))[cle]
    return MC.issues(runs), MC.bootstrap(runs, lambda r: r["fin"] == "arrivee"), len(runs)


def ic(t):
    from sim.rapport_mc import ic as _ic
    return _ic(t)


def afficher_tache(tid: str, cle: str):
    """Barre de progression, journal et bouton d'annulation d'une tâche ; se rafraîchit toutes les 2 s
    tant qu'elle tourne (seul ce bloc est réexécuté, pas la page)."""
    en_cours = T.etat(tid)["statut"] == "en_cours"

    @st.fragment(run_every=2 if en_cours else None)
    def _bloc():
        e = T.etat(tid)
        st.progress(e["progression"], text=f"{e['titre']} — {e['statut'].replace('_', ' ')}")
        c1, c2 = st.columns([1, 5])
        if e["statut"] == "en_cours":
            if c1.button("Annuler", key=f"annuler_{cle}_{tid}"):
                T.annuler(tid)
                st.rerun()
            c2.caption(f"démarrée il y a {(time.time() - e['debut']) / 60:.1f} min")
        else:
            duree = (e.get("fin", time.time()) - e["debut"]) / 60
            c2.caption(f"durée {duree:.1f} min")
        with st.expander("Journal", expanded=e["statut"] == "erreur"):
            st.code("\n".join(e["log"].splitlines()[-40:]) or "(vide)", language=None)
        if e["statut"] == "termine":
            prod = T.fichiers_produits(e["log"])
            if prod:
                st.caption("Fichiers produits : " + ", ".join(Path(p).name for p in prod))
    _bloc()


def markdown_avec_images(texte: str, base: Path = OUT):
    """Markdown du rapport : les images (chemins relatifs à out/) sont affichées par st.image, les liens
    vers les cartes HTML restent des liens."""
    import re
    pos = 0
    for m in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", texte):
        st.markdown(texte[pos:m.start()])
        figure(base / m.group(2), m.group(1) or None)
        pos = m.end()
    st.markdown(texte[pos:])


def figure(f: Path, legende: str | None = None):
    if f.exists():
        st.image(str(f), caption=legende, width="stretch")


# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------
def page_configuration():
    st.header("Configuration")
    st.write("Les modifications sont enregistrées dans une **copie** (dossier `configs/`). L'original "
             "`config.yaml` n'est remplacé qu'après confirmation, avec une sauvegarde `config.yaml.bak`.")
    source = choisir_config("cfg_source", "point de départ du formulaire")
    cfg = C.charger(source)
    noms = noms_solutions()
    with st.form("form_config"):
        st.subheader("Mission")
        c1, c2, c3 = st.columns(3)
        d0 = dt.date.fromisoformat(cfg["mission"]["start"][:10])
        date = c1.date_input("Date de largage (12:00 UTC)", d0)
        lat_d = c2.number_input("Largage : latitude (°N)", value=float(cfg["mission"]["depart"]["lat"]), step=0.5)
        lon_d = c3.number_input("Largage : longitude (°E, négatif à l'ouest)", value=float(cfg["mission"]["depart"]["lon"]),
                                step=0.5)
        c1, c2, c3 = st.columns(3)
        lat_a = c1.number_input("Cercle d'arrivée : latitude", value=float(cfg["mission"]["arrivee"]["lat"]), step=0.5)
        lon_a = c2.number_input("Cercle d'arrivée : longitude", value=float(cfg["mission"]["arrivee"]["lon"]), step=0.5)
        rayon = c3.number_input("Rayon du cercle (km)", value=float(cfg["mission"]["arrivee"]["rayon_km"]), step=5.0)

        st.subheader("Solutions S1–S20")
        cols = st.columns(4)
        etats = {}
        for i, (s, v) in enumerate(cfg["solutions"].items()):
            etats[s] = cols[i % 4].selectbox(f"{s} {noms.get(s, '')}", ETATS, index=ETATS.index(v),
                                             format_func=LIB_ETATS.get, key=f"sol_{s}")

        st.subheader("Batterie et chauffage")
        b = cfg["bateau"]["batterie"]
        ch = b["chauffage"]
        c1, c2, c3 = st.columns(3)
        cap = c1.number_input("Capacité (Wh)", value=float(b["capacite_wh"]), step=20.0)
        soc0 = c2.slider("Charge au largage", 0.0, 1.0, float(b["soc_initial"]), 0.05)
        dts = c3.number_input("Batterie : écart à la mer (°C)", value=float(b["delta_t_sur_mer_c"]), step=0.5)
        c1, c2, c3, c4 = st.columns(4)
        ch_act = c1.checkbox("Chauffage actif", value=bool(ch["active"]))
        ch_mode = c2.selectbox("Mode", ["quand_soleil", "toujours"], index=["quand_soleil", "toujours"].index(ch["mode"]))
        ch_cons = c3.number_input("Consigne (°C)", value=float(ch["consigne_c"]), step=1.0)
        ch_p = c4.number_input("Puissance max (W)", value=float(ch["puissance_max_w"]), step=1.0)

        st.subheader("Calcul")
        c1, c2 = st.columns(2)
        n_runs = c1.number_input("Runs par Monte-Carlo", 25, 5000, int(cfg["simulation"]["n_runs"]), step=25)
        n_cf = c2.number_input("Runs par contrefactuel", 25, 2000, int(cfg["simulation"]["n_runs_contrefactuel"]), step=25)

        st.subheader("Enregistrer")
        nom_copie = st.text_input("Nom de la copie", value=f"config_{date:%Y%m%d}.yaml")
        ok = st.form_submit_button("Enregistrer la copie", type="primary")

    if ok:
        c = copy.deepcopy(cfg)
        c["mission"]["start"] = f"{date:%Y-%m-%d}T12:00:00Z"
        c["mission"]["depart"].update(lat=lat_d, lon=lon_d)
        c["mission"]["arrivee"].update(lat=lat_a, lon=lon_a, rayon_km=rayon)
        c["solutions"] = etats
        b = c["bateau"]["batterie"]
        b.update(capacite_wh=cap, soc_initial=soc0, delta_t_sur_mer_c=dts)
        b["chauffage"].update(active=ch_act, mode=ch_mode, consigne_c=ch_cons, puissance_max_w=ch_p)
        c["simulation"].update(n_runs=int(n_runs), n_runs_contrefactuel=int(n_cf))
        nom = Path(nom_copie).name
        if not nom.endswith(".yaml"):
            nom += ".yaml"
        CONFIGS.mkdir(exist_ok=True)
        f = CONFIGS / nom
        f.write_text("# Copie générée par l'interface (app.py) à partir de " + source.name + "\n"
                     + yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
        st.session_state["config_courante"] = f"configs/{nom}"
        st.success(f"Copie enregistrée : configs/{nom}. Elle est sélectionnée dans les autres onglets.")

    with st.expander("Remplacer l'original config.yaml par une copie"):
        copies = [k for k in fichiers_config() if k.startswith("configs/")]
        if not copies:
            st.caption("Aucune copie enregistrée.")
        else:
            choix = st.selectbox("Copie à installer", copies)
            conf = st.checkbox("Je confirme : config.yaml sera remplacé (sauvegarde dans config.yaml.bak ; "
                               "les commentaires de l'original seront perdus).")
            if st.button("Remplacer config.yaml", disabled=not conf):
                shutil.copy2(ORIGINAL, ORIGINAL.with_suffix(".yaml.bak"))
                shutil.copy2(fichiers_config()[choix], ORIGINAL)
                st.success("config.yaml remplacé ; ancien fichier : config.yaml.bak")


# ---------------------------------------------------------------------------
# 2. Lancer
# ---------------------------------------------------------------------------
def page_lancer():
    st.header("Lancer un calcul")
    f = choisir_config("cfg_lancer")
    cfg = C.charger(f)
    st.caption(f"Départ {cfg['mission']['start'][:10]}, solutions validées : "
               f"{sum(v == 'validee' for v in cfg['solutions'].values())}/20, "
               f"partielles : {sum(v == 'partielle' for v in cfg['solutions'].values())}/20")
    quoi = st.radio("Calcul", ["Une mission (carte, courbes, journal)", "Monte-Carlo", "Rapport complet"],
                    horizontal=True)
    args = ["--config", str(f)]
    if quoi.startswith("Une mission"):
        c1, c2 = st.columns(2)
        graine = c1.number_input("Graine", value=int(cfg["simulation"]["graine"]), step=1)
        jeu = c2.number_input("Jeu de paramètres (0–24)", 0, 24, 0)
        cmd = ["simuler", *args, "--graine", str(graine), "--jeu", str(jeu), "--etiquette", f.stem]
        titre = f"Mission {f.stem}, graine {graine}"
    elif quoi == "Monte-Carlo":
        n = st.number_input("Runs", 25, 5000, int(cfg["simulation"]["n_runs"]), step=25)
        cmd = ["montecarlo", *args, "--runs", str(n), "--etiquette", f.stem]
        titre = f"Monte-Carlo {f.stem} ({n} runs)"
    else:
        c1, c2, c3 = st.columns(3)
        n = c1.number_input("Runs (référence)", 25, 5000, int(cfg["simulation"]["n_runs"]), step=25)
        ncf = c2.number_input("Runs par contrefactuel", 25, 2000, int(cfg["simulation"]["n_runs_contrefactuel"]), step=25)
        ete = c3.checkbox("Comparaison d'été", value=True)
        cmd = ["rapport", *args, "--runs", str(n), "--runs-cf", str(ncf)] + ([] if ete else ["--sans-ete"])
        titre = f"Rapport complet {f.stem} ({n} runs)"
        st.info("Environ 8 minutes pour 500 runs sur 14 processus. L'interface reste utilisable pendant le calcul.")
    if st.button("Lancer", type="primary"):
        st.session_state["derniere_tache"] = T.lancer(cmd, titre)
    st.divider()
    st.subheader("Tâches")
    taches = T.lister()
    if not taches:
        st.caption("Aucune tâche.")
    for e in taches[:8]:
        afficher_tache(e["id"], "lancer")


# ---------------------------------------------------------------------------
# 3. Résultats
# ---------------------------------------------------------------------------
def page_resultats():
    st.header("Résultats")
    t_mission, t_mc, t_pb, t_rapport = st.tabs(["Mission", "Monte-Carlo", "P1–P28 et solutions", "Rapport"])
    with t_mission:
        cartes = sorted(OUT.glob("*_carte.html"), key=lambda p: -p.stat().st_mtime)
        if not cartes:
            st.caption("Aucune mission simulée : onglet « Lancer ».")
        else:
            nom = st.selectbox("Mission", [c.name[:-len("_carte.html")] for c in cartes])
            import streamlit.components.v1 as components
            components.html((OUT / f"{nom}_carte.html").read_text(encoding="utf-8"), height=560)
            figure(OUT / f"{nom}_courbes.png", "Énergie, vitesse, état de mer, largeur de la boîte Codac")
            j = OUT / f"{nom}_journal.md"
            if j.exists():
                with st.expander("Journal de bord", expanded=False):
                    st.markdown(j.read_text(encoding="utf-8"))
    with t_mc:
        fichiers = sorted(OUT.glob("mc_reference_*.json"), key=lambda p: -p.stat().st_mtime)
        if not fichiers:
            st.caption("Aucun Monte-Carlo : onglet « Lancer ».")
        else:
            f = st.selectbox("Monte-Carlo", [x.name for x in fichiers])
            fj = OUT / f
            et = f[len("mc_reference_"):-len(".json")]
            cles = list(charger_json(fj))
            cols = st.columns(len(cles))
            for col, cle in zip(cols, cles):
                iss, arr, n = _issues(str(fj), fj.stat().st_mtime, cle)
                col.metric(f"P(arrivée) — {cle.replace('_', ' ')} ({n} runs)", f"{100 * arr[0]:.0f} %",
                           help=f"intervalle à 90 % : {ic(arr)}")
                col.markdown("| Issue | Probabilité [90 %] |\n|---|---|\n" + "\n".join(
                    f"| {k} | {ic(v)} |" for k, v in sorted(iss.items(), key=lambda x: -x[1][0])))
            for pre, leg in (("mc_issues_", "Issues"), ("mc_issues_toutvalide_", "Issues, tout validé"),
                             ("mc_jours_", "Jour de fin"), ("mc_positions_", "Positions finales")):
                figure(OUT / f"{pre}{et}.png", leg)
    with t_pb:
        ref = sorted(OUT.glob("mc_cf_ajout_*.json"), key=lambda p: -p.stat().st_mtime)
        if not ref:
            st.caption("Lancer un rapport complet pour obtenir le tableau P1–P28 et la valeur des solutions.")
        else:
            et = ref[0].name[len("mc_cf_ajout_"):-len(".json")]
            st.caption(f"Rapport du {et}")
            tableau_problemes_et_solutions(et)
    with t_rapport:
        rapports = sorted(OUT.glob("rapport_*.md"), key=lambda p: -p.stat().st_mtime)
        if rapports:
            r = st.selectbox("Rapport", [x.name for x in rapports])
            texte = (OUT / r).read_text(encoding="utf-8")
            st.download_button("Télécharger", texte, file_name=r)
            markdown_avec_images(texte)
        else:
            st.caption("Aucun rapport.")


@st.cache_data(show_spinner="Tableau P1–P28 (bootstrap)…")
def _tableaux(et: str, mtime: float):
    from sim import montecarlo as MC
    from sim import rapport_mc as RM
    from sim import risks as RK
    base = MC.charger(f"reference_{et}")["actuel"]
    cf_aj = MC.charger(f"cf_ajout_{et}")
    cf_re = MC.charger(f"cf_retrait_{et}")
    reg = RK.charger_registre()
    t_pb = RM.tableau_problemes(reg, base, cf_aj)
    succes = lambda r: r["fin"] == "arrivee"  # noqa: E731
    g_aj = RM.gains_solutions(cf_aj, succes)
    ref = cf_re["reference"]
    g_re = {s: MC.bootstrap_diff(runs, ref, succes) for s, runs in cf_re.items() if s != "reference"}
    noms = RM.NOMS_S
    L = ["| Solution | Gain si on la valide (config actuelle) | Perte si on la retire (tout le reste validé) |",
         "|---|---|---|"]
    for s in sorted(set(g_aj) | set(g_re), key=lambda s: -(g_re.get(s, (0,))[0])):
        a = ic(g_aj[s]) if s in g_aj else "(déjà validée)"
        b = ic(g_re[s]) if s in g_re else ""
        L.append(f"| {s} {noms.get(s, '')} | {a} | {b} |")
    return "\n".join(t_pb), "\n".join(L)


def tableau_problemes_et_solutions(et):
    f = OUT / f"mc_cf_retrait_{et}.json"
    t_pb, t_sol = _tableaux(et, f.stat().st_mtime if f.exists() else 0.0)
    st.subheader("Problèmes P1–P28 (configuration actuelle)")
    st.markdown(t_pb)
    st.subheader("Valeur de chaque solution (points de probabilité d'arrivée, intervalle à 90 %)")
    st.markdown(t_sol)
    c1, c2 = st.columns(2)
    with c1:
        figure(OUT / f"valeur_ajout_{et}.png")
    with c2:
        figure(OUT / f"valeur_retrait_{et}.png")


# ---------------------------------------------------------------------------
# 4. Comparer
# ---------------------------------------------------------------------------
FICHIER_CMP = OUT / "taches" / "comparaisons.json"


def page_comparer():
    st.header("Comparer deux configurations")
    st.write("Mêmes graines et mêmes jeux de paramètres pour les deux configurations : la différence est "
             "calculée run par run (nombres aléatoires communs), donc plus précise que deux intervalles séparés.")
    c1, c2 = st.columns(2)
    cfgs = {}
    for col, k in ((c1, "A"), (c2, "B")):
        with col:
            st.subheader(f"Configuration {k}")
            f = choisir_config(f"cmp_{k}")
            cfg = C.charger(f)
            d = st.date_input("Date de largage", dt.date.fromisoformat(cfg["mission"]["start"][:10]), key=f"date_{k}")
            cfgs[k] = (f, d)
    n = st.number_input("Runs par configuration", 25, 2000, 200, step=25)
    if st.button("Comparer", type="primary"):
        stamp = time.strftime("%H%M%S")
        paire = {}
        for k, (f, d) in cfgs.items():
            etq = f"cmp{k}_{stamp}"
            tid = T.lancer(["montecarlo", "--config", str(f), "--start", f"{d:%Y-%m-%d}", "--runs", str(n),
                            "--etiquette", etq], f"Comparaison {k} : {f.stem}, {d}")
            paire[k] = {"tache": tid, "etiquette": etq, "nom": f"{f.stem} ({d:%d/%m/%Y})"}
        FICHIER_CMP.parent.mkdir(parents=True, exist_ok=True)
        hist = json.loads(FICHIER_CMP.read_text(encoding="utf-8")) if FICHIER_CMP.exists() else []
        FICHIER_CMP.write_text(json.dumps([paire] + hist[:9]), encoding="utf-8")
    if not FICHIER_CMP.exists():
        return
    hist = json.loads(FICHIER_CMP.read_text(encoding="utf-8"))
    choix = st.selectbox("Comparaison", range(len(hist)),
                         format_func=lambda i: f"{hist[i]['A']['nom']}  contre  {hist[i]['B']['nom']}")
    paire = hist[choix]
    fini = True
    for k in ("A", "B"):
        e = T.etat(paire[k]["tache"])
        if e["statut"] != "termine":
            fini = False
            afficher_tache(paire[k]["tache"], f"cmp{k}")
    if not fini:
        return
    from sim import montecarlo as MC
    from sim import rapport_mc as RM
    ra = MC.charger(f"reference_{paire['A']['etiquette']}")["reference"]
    rb = MC.charger(f"reference_{paire['B']['etiquette']}")["reference"]
    succes = lambda r: r["fin"] == "arrivee"  # noqa: E731
    c1, c2, c3 = st.columns(3)
    c1.metric(f"A — {paire['A']['nom']}", ic(MC.bootstrap(ra, succes)))
    c2.metric(f"B — {paire['B']['nom']}", ic(MC.bootstrap(rb, succes)))
    c3.metric("B − A (apparié)", ic(MC.bootstrap_diff(ra, rb, succes)))
    nom = f"cmp_{paire['A']['etiquette']}"
    f = OUT / f"{nom}.png"
    if not f.exists():
        RM.figure_comparaison(ra, rb, (f"A — {paire['A']['nom']}", f"B — {paire['B']['nom']}"), nom,
                              "Issues de la mission : A contre B")
    figure(f)
    c1, c2 = st.columns(2)
    for col, k in ((c1, "A"), (c2, "B")):
        with col:
            figure(OUT / f"mc_positions_{paire[k]['etiquette']}.png", f"Positions finales — {paire[k]['nom']}")
            figure(OUT / f"mc_jours_{paire[k]['etiquette']}.png", f"Jour de fin — {paire[k]['nom']}")


# ---------------------------------------------------------------------------
# 5. Mode histoire
# ---------------------------------------------------------------------------
class _Question(Exception):
    def __init__(self, texte):
        super().__init__(texte)
        self.texte = texte


def _jouer_histoire(chemin_cfg: str, mtime: float, graine: int, jeu: int, reponses: dict):
    """Rejoue l'histoire avec les réponses déjà données ; s'arrête à la première question sans réponse."""
    from sim import story
    cfg = C.charger(chemin_cfg)
    ctx = contexte(str(grille_pour(cfg)))
    lignes = []
    question = None

    def entree(q):
        raise _Question(q)
    try:
        r, _ = story.mode_histoire(cfg, ctx, graine=graine, jeu_k=jeu, reponses=reponses, entree=entree,
                                   sortie=lignes.append)
    except _Question as q:
        question, r = q.texte, None
    return lignes, question, r


def page_histoire():
    st.header("Mode histoire")
    st.write("La mission avance jour par jour sur la météo réelle. À chaque incident grave, dites si la solution "
             "est en place : l'histoire est rejouée avec la même météo et les mêmes tirages.")
    f = choisir_config("cfg_histoire")
    cfg = C.charger(f)
    c1, c2, c3 = st.columns([2, 2, 1])
    graine = c1.number_input("Graine", value=int(cfg["simulation"]["graine"]), step=1, key="h_graine")
    jeu = c2.number_input("Jeu de paramètres", 0, 24, 0, key="h_jeu")
    cle = (str(f), int(graine), int(jeu))
    if st.session_state.get("h_cle") != cle or c3.button("Recommencer"):
        st.session_state["h_cle"] = cle
        st.session_state["h_rep"] = {}
    rep = st.session_state["h_rep"]
    with st.spinner("Simulation…"):
        lignes, question, r = _jouer_histoire(str(f), f.stat().st_mtime, int(graine), int(jeu), dict(rep))
    st.code("\n".join(lignes), language=None)
    if question:
        import re
        m = re.search(r"solution (S\d+)", question)
        s = m.group(1) if m else None
        st.warning(question.strip().replace(" [o/n/partielle]", ""))
        b1, b2, b3 = st.columns(3)
        for col, lab, val in ((b1, "Oui, validée", "o"), (b2, "Partielle", "partielle"), (b3, "Non", "n")):
            if col.button(lab, key=f"rep_{s}_{val}", width="stretch"):
                rep[s] = val
                st.rerun()
    elif r is not None:
        st.success("Histoire terminée.")
        if st.button("Carte et courbes de cette histoire"):
            from sim import carte, report
            nom = f"histoire_gui_g{graine}"
            carte.carte_folium(cfg, r, f"{nom}_carte", "Mode histoire")
            report.courbes_run(cfg, r, f"{nom}_courbes", "Mode histoire")
            import streamlit.components.v1 as components
            components.html((OUT / f"{nom}_carte.html").read_text(encoding="utf-8"), height=520)
            figure(OUT / f"{nom}_courbes.png")


# ---------------------------------------------------------------------------
# 6. Données
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Inventaire du cache…", ttl=60)
def _inventaire():
    from sim import environment as E
    cfg = C.charger()
    lignes = []
    for cle, lib in (("grille", "grille principale (2°)"), ("grille_fine", "couloir fin (1°)")):
        res = E.etat_cache(cfg, cfg["donnees"][cle])
        fait, tot = sum(n for n, _ in res.values()), sum(t for _, t in res.values())
        lignes.append((f"{E.annee_de_base(cfg)} — {lib}", fait, tot, (DATA / E.nom_grille(cfg["donnees"][cle])).exists()))
    for a in cfg["donnees"].get("annees", []):
        if int(a) == E.annee_de_base(cfg):
            continue
        res = E.etat_cache(cfg, cfg["donnees"]["grille"], E.periode_annee(cfg, a))
        fait, tot = sum(n for n, _ in res.values()), sum(t for _, t in res.values())
        lignes.append((f"{a} — grille principale (2°)", fait, tot,
                       (DATA / E.nom_grille(cfg["donnees"]["grille"], a, cfg)).exists()))
    autres = [("Pêche et trafic (Global Fishing Watch)", (DATA / "gfw.npz").exists()),
              ("Trait de côte (Natural Earth)", (DATA / "cote.wkb").exists()),
              ("Icebergs (International Ice Patrol, désactivé par défaut)", (DATA / "icebergs.csv").exists())]
    return lignes, autres, str(E.chemin_grille(cfg, strict=False))


def page_donnees():
    st.header("État des données")
    lignes, autres, grille = _inventaire()
    st.markdown("| Données météo et mer (Open-Meteo, ERA5) | Fichiers point × mois | Grille assemblée |\n|---|---|---|\n"
                + "\n".join(f"| {n} | {f} / {t} {'✅' if f >= t else '⏳'} | {'oui' if g else 'non'} |"
                            for n, f, t, g in lignes))
    st.markdown("| Autres sources | En cache |\n|---|---|\n" + "\n".join(f"| {n} | {'oui' if ok else 'non'} |"
                                                                       for n, ok in autres))
    st.caption(f"Grille utilisée pour simuler : {Path(grille).name if grille != 'None' else 'aucune'}")
    st.subheader("Reprendre le téléchargement")
    st.write("Quota Open-Meteo : 10 000 requêtes pondérées par jour. Le téléchargeur s'arrête de lui-même au quota "
             "et reprend là où il en était au lancement suivant (le lendemain). Le jeton Global Fishing Watch est "
             "lu dans `secrets.yaml`, jamais affiché ni copié.")
    c1, c2, c3 = st.columns(3)
    fine = c1.checkbox("Couloir fin (1°)", value=True)
    annees = c2.checkbox("Années supplémentaires", value=True)
    gfw = c3.checkbox("Global Fishing Watch", value=False)
    if st.button("Reprendre", type="primary"):
        args = ["donnees"] + (["--fine"] if fine else []) + (["--annees"] if annees else []) + ([] if gfw else ["--sans-gfw"])
        st.session_state["tache_donnees"] = T.lancer(args, "Téléchargement des données")
        _inventaire.clear()
    if st.session_state.get("tache_donnees"):
        afficher_tache(st.session_state["tache_donnees"], "donnees")


# ---------------------------------------------------------------------------
PAGES = {"Configuration": page_configuration, "Lancer": page_lancer, "Résultats": page_resultats,
         "Comparer": page_comparer, "Mode histoire": page_histoire, "Données": page_donnees}

st.sidebar.title("🐢 Epi'Tortue")
st.sidebar.caption("Simulateur de mission Microtransat. Scénarios plausibles, pas des prédictions : chaque "
                   "probabilité est donnée avec son intervalle à 90 %.")
page = st.sidebar.radio("Onglet", list(PAGES))
PAGES[page]()
