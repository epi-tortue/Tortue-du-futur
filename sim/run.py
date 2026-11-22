"""Boucle de simulation d'une mission Epi'Tortue.

Modules (activables dans cfg["simulation"]["modules"] ou par argument) :
  energie     : solaire réel + batterie + chauffage + gestion S8   (sinon puissance constante)
  estimateur  : localisation Codac + pannes GPS/compas              (sinon GPS parfait)
  risques     : registre P1–P28, rencontres de pêche, collisions, cascades
L'autopilote navigue TOUJOURS sur la position estimée (centre de la boîte Codac).

Une mission a deux fins distinctes :
  - fin de mission (cause_fin) : le premier événement qui rend l'arrivée impossible ou
    l'invalide (disqualification, épave, capture…) ;
  - devenir physique (issue_physique) : ce qu'il advient du bateau ensuite (dérive jusqu'à
    la côte, récupéré, coulé…), simulé en mode « épave » à pas long.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from . import boat as B
from . import energy as EN
from .autopilot import Autopilote, cap_crabe
from .environment import Environnement, charger_cote
from .failures import Aleas, Capteurs
from .geo import NM, cap_initial, deplacer, haversine
from .risks import facteur_lacet as RK_facteur_lacet

MODULES_DEFAUT = {"energie": True, "estimateur": True, "risques": True}


@dataclass
class Evenement:
    t: float
    lat: float
    lon: float
    type: str
    texte: str
    probleme: str | None = None
    gravite: int = 1          # 0 info, 1 incident, 2 grave, 3 fin de mission


@dataclass
class Resultat:
    traj: dict
    evenements: list
    fin: str                       # cause de fin de mission
    t_fin: float                   # instant de fin de mission
    issue_physique: str = ""
    t_fin_physique: float = 0.0
    retrouve: bool = True          # position finale connue (télémétrie / balise / récupéré)
    occurrences: dict = field(default_factory=dict)
    premiere: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    graine: int = 0
    jeu: int = 0
    solutions: dict = field(default_factory=dict)
    config_resume: dict = field(default_factory=dict)

    @property
    def jours(self) -> float:
        return (self.t_fin - self.traj["t"][0]) / 86400.0

    @property
    def succes(self) -> bool:
        return self.fin == "arrivee"


def t_epoch(iso_: str) -> float:
    d = datetime.fromisoformat(iso_.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")


class Simulation:
    def __init__(self, cfg: dict, env: Environnement | None = None, cote=None, p_constante: float | None = None,
                 modules: dict | None = None, graine: int | None = None, jeu=None, densites=None,
                 registre_yaml: dict | None = None, dt: float | None = None, enregistrer_tout: bool = True,
                 champs_traj: tuple | None = None):
        self.cfg = cfg
        self.env = env or Environnement()
        self.terre, self.terre_prep = cote or charger_cote()
        from .environment import masque_cote
        self.masque = masque_cote((self.terre, self.terre_prep))
        self.coque = B.Coque.depuis_config(cfg)
        self.ap = Autopilote.depuis_config(cfg)
        self.dt = float(dt or cfg["simulation"]["dt_dynamique_s"])
        self.modules = dict(MODULES_DEFAUT)
        self.modules.update(cfg["simulation"].get("modules", {}) or {})
        if modules:
            self.modules.update(modules)
        if p_constante is not None:
            self.modules["energie"] = False
        self.p_constante = p_constante if p_constante is not None else cfg["bateau"]["propulsion"]["p_croisiere_w"]
        self.graine = int(cfg["simulation"]["graine"] if graine is None else graine)
        self.aleas = Aleas(self.graine)
        self.enregistrer_tout = enregistrer_tout
        # champs_traj : n'enregistrer que ces séries (Monte-Carlo : le résumé n'en lit que quelques-unes).
        # Les champs relus par la boucle elle-même (v_surf, mode, t) sont toujours gardés.
        self.champs_traj = None if champs_traj is None else tuple(dict.fromkeys(("t", "v_surf", "mode") + tuple(champs_traj)))
        from .icebergs import Icebergs
        self.icebergs = Icebergs.depuis_config(cfg)          # None si désactivé (défaut) [H08]
        self.registre = None
        if self.modules["risques"]:
            from . import risks as RK
            reg = RK.registre_pour(cfg, registre_yaml or RK.charger_registre())
            dens = densites or RK.Densites()
            jeu = jeu or RK.tirer_parametres(reg, cfg, 0, dens)
            self.registre = RK.Registre(reg, cfg, jeu, self.aleas, dens)
            self.densites = dens
        else:
            self.densites = densites

    # ==================================================================
    def sol(self, s):
        return self.cfg["solutions"].get(s, "absente")

    def _ev(self, type_, texte, pid=None, gravite=1, t=None):
        self.evts.append(Evenement(self.t if t is None else t, self.lat, self.lon, type_, texte, pid, gravite))

    def terminer(self, cause, texte, epave=True, pid=None):
        if self.cause_fin is None:
            self.cause_fin = cause
            self.t_fin_mission = self.t
            self.cause_pid = pid or getattr(self, "_pid_courant", None) or self._cause_par_defaut(cause)
            if self.registre is not None:       # problèmes survenus PENDANT la mission
                self._occ_mission = dict(self.registre.occurrences)
                self._prem_mission = dict(self.registre.premiere)
            self._ev("fin_mission", texte, gravite=3)
        if epave:
            self.epave = True

    # ==================================================================
    def executer(self) -> Resultat:
        from shapely.geometry import LineString

        cfg = self.cfg
        t0 = t_epoch(cfg["mission"]["start"])
        if t0 < self.env.t_debut:
            raise ValueError("Date de départ antérieure aux données en cache")
        self.t0 = t0
        t_max = min(t0 + cfg["mission"]["max_days"] * 86400.0, self.env.t_fin - 3600.0)
        if t_max <= t0:
            raise ValueError("Aucune donnée après la date de départ")
        self.t = t0
        self.lat, self.lon = cfg["mission"]["depart"]["lat"], cfg["mission"]["depart"]["lon"]
        arr = cfg["mission"]["arrivee"]
        rayon = arr["rayon_km"] * 1000.0
        nav = cfg["navigation"]
        self.evts: list[Evenement] = []
        self.cause_fin = None
        self.cause_pid = None
        self._pid_courant = None
        self._silence_pid = None
        self.t_fin_mission = None
        self.epave = False
        issue_phys = None
        retrouve = True

        # --- sous-systèmes ---------------------------------------------------
        e0 = self.env.echantillon(t0, self.lat, self.lon)
        bat = EN.Batterie.depuis_config(cfg, float(e0["sst"]) + cfg["bateau"]["batterie"]["delta_t_sur_mer_c"])
        gest = EN.GestionEnergie(self.sol("S8"), cfg)
        capt = Capteurs(cfg, self.aleas)
        est = None
        if self.modules["estimateur"]:
            from .estimator_codac import EstimateurCodac
            est = EstimateurCodac(cfg, self.lat, self.lon, t0)
        R = self.registre
        p9 = {"modele": "puissance"}
        p9_sigma = 0.0
        if R is not None:
            p9 = dict(R.reg["problemes"]["P9"])
            p9.setdefault("modele", "puissance")
            if p9["modele"] != "puissance":
                p9_sigma = float(R.param("P9", "lacet_sigma_deg"))
            P15 = R.param_solution("P15", "effet_capteurs", "S9")
            mP18 = R.multiplicateur("P18")
            capt.mult_gps = capt.mult_compas = P15 * mP18

        s = dict(calc="ok", gel_permanent=False, moteur_hs=False, helice=False, barre="ok", circuits=2 if self.sol("S6") != "absente" else 1,
                 circuits_ok=None, iridium=True, reception=True, chavire=False, t_chavire=None, drains=False,
                 bug_cap=None, blocage_moteur=False, failsafe=False, fouling=0.0, redemarrages=0, voie_eau=0.0,
                 p_moteur_gel=0.0, cap_gel=None, perte_vmg=0.0, t_bug=0.0, t_failsafe=0.0)
        s["circuits_ok"] = s["circuits"]
        balise = False
        if R is not None:
            balise = R.tirage("balise_fiable") < R.param_solution("P27", "balise_fiable", "S18")
        ais_ok = self.sol("S15") != "absente"
        t_rapport = t0
        silence_cumul = 0.0
        disq = False
        t_bug49 = t0 + 49.71 * 86400.0
        bug49_fait = False
        stats = dict(e_solaire=0.0, e_moteur=0.0, e_hotel=0.0, e_chauffage=0.0, e_ecretee=0.0, e_froid_bloquee=0.0,
                     wh_charge_froid=0.0, blackouts=0, rapports=0, fix_rejetes=0, sauts_gps=0, hors_boite=0,
                     hors_boite_t=[], dist_parcourue_nm=0.0)
        du_est = dv_est = 0.0
        cap = float(cap_initial(self.lat, self.lon, arr["lat"], arr["lon"]))
        cap_bug_val = None

        keys = ["t", "lat", "lon", "cap", "v_surf", "v_fond", "p_moteur", "p_solaire", "p_chauffage", "soc_pct",
                "t_bat", "dist_restante_nm", "encrassement", "vent", "rafales", "hs", "courant", "sst", "t_air",
                "ghi", "estime_lat", "estime_lon", "boite_km", "contient", "gps", "mode", "peche"]
        if self.champs_traj is not None:
            keys = [k for k in keys if k in self.champs_traj]
        rec = {k: [] for k in keys}
        traj_complete = self.champs_traj is None
        boites = []          # (t, lat0, lat1, lon0, lon1) pendant les pertes GPS (1/h)
        dt_nominal = self.dt

        while True:
            dt = self.dt if not self.epave else max(self.dt, 3 * 3600.0)
            t = self.t
            ev = self.env.vecteur(t, self.lat, self.lon).tolist()      # flottants Python (mêmes valeurs)
            ix = self.env.idx
            e = {k: ev[ix[k]] for k in ("vent_u", "vent_v", "rafales", "hs", "vague_dir_u", "vague_dir_v",
                                        "courant_u", "courant_v", "sst", "t_air", "dni_h", "dhi", "ghi", "tp")}
            jours = (t - t0) / 86400.0
            peche = self.densites.peche_h_km2(self.lat, self.lon, t) if self.densites is not None else 0.0

            # ---------------------------------------------------------------- énergie
            calc_actif = s["calc"] in ("ok", "gele") and not self.epave
            p_pv = 0.0
            p_heat = 0.0
            if self.modules["energie"]:
                fpv = s["circuits_ok"] / s["circuits"]
                p_pv = 0.0 if s["chavire"] else EN.p_solaire(cfg, t, self.lat, self.lon, e["dni_h"], e["dhi"], fpv)
                if s["fouling"] > 0:
                    p_pv *= max(0.5, 1 - 0.2 * s["fouling"])        # salissure des panneaux [H15]
                gest.maj_moyenne(p_pv, dt)
                if gest.prevision_active and s["calc"] in ("ok", "veille") and not self.epave:
                    # S8 validée, politique « prevision » : veille de nuit décidée sur la prévision solaire [H74]
                    f_prev = 0.0 if s["chavire"] else fpv * (max(0.5, 1 - 0.2 * s["fouling"]) if s["fouling"] > 0 else 1.0)
                    gest.planifier(self.env, t, self.lat, self.lon, bat, p_pv, f_prev, dt, s["iridium"], ais_ok,
                                   s["reception"])
                    if gest.veille and s["calc"] == "ok":
                        s["calc"] = "veille"
                        if not stats.get("veilles"):
                            self._ev("veille", "Énergie comptée : le bateau passe en veille profonde pour la nuit "
                                     "(moteur coupé, calculateur endormi, position toujours transmise) ; il en sera "
                                     "ainsi chaque nuit tant que le soleil manquera", "P12", 0)
                        stats["veilles"] = stats.get("veilles", 0) + 1
                    elif not gest.veille and s["calc"] == "veille":
                        s["calc"] = "ok"
                elif s["calc"] == "veille":
                    s["calc"] = "ok"
                calc_actif = s["calc"] in ("ok", "gele") and not self.epave
                if s["calc"] == "eteint":
                    hotel = 0.0
                elif s["calc"] == "veille":
                    hotel = gest.hotel_veille(s["iridium"], ais_ok)
                else:
                    hotel = gest.charge_hotel(s["iridium"], ais_ok, True)
            else:
                hotel = 0.0

            # ---------------------------------------------------------------- navigation : cible et cap
            if est is not None:
                lat_e, lon_e = est.centre_geo()
                largeur_km = est.largeur_m() / 1000.0
            else:
                lat_e, lon_e, largeur_km = self.lat, self.lon, 0.0
            mode = "normal"
            fraction = 1.0
            cap_cmd = None                                         # cap à tenir (vrai) ou None = pas de contrôle
            gouvernable = s["barre"] in ("ok", "secours")
            if self.epave:
                mode = "epave"
            elif s["calc"] == "eteint":
                mode = "black-out"
            elif s["calc"] == "veille":
                mode = "veille"
            elif s["calc"] == "gele":
                mode = "gel"
            elif s["bug_cap"] is not None:
                mode = "bug_cap"
                cap_cmd = s["bug_cap"]
                if t - s["t_bug"] > 5 * 86400 and self.cause_fin is None:
                    self.terminer("logiciel", "Fin de mission : le logiciel tient un cap erroné depuis 5 jours",
                                  epave=False, pid="P16")
            elif s["blocage_moteur"]:
                mode = "bug_moteur"
                if t - s["t_bug"] > 5 * 86400 and self.cause_fin is None:
                    self.terminer("logiciel", "Fin de mission : moteur bloqué à l'arrêt par le logiciel depuis 5 jours",
                                  epave=False, pid="P16")
            else:
                compas_fiable = not (est is not None and est.compas_hs) and not capt.compas.hs
                gps_ok = capt.gps.disponible(t)
                if s["failsafe"]:
                    mode = "failsafe_retour"
                    if t - s["t_failsafe"] > 10 * 86400 and self.cause_fin is None:
                        self.terminer("failsafe", "Fin de mission : le failsafe ramène le bateau vers son point de "
                                      "départ depuis 10 jours", epave=False, pid="P17")
                    d0 = cfg["mission"]["depart"]
                    route = float(cap_initial(lat_e, lon_e, d0["lat"], d0["lon"]))
                else:
                    route = None
                if largeur_km > nav["seuil_degrade_km"] and not s["failsafe"]:
                    mode = "degrade"
                    fraction = nav["fraction_puissance_degrade"]
                    cap_cmd = math.radians(nav["cap_degrade_deg"])
                else:
                    v_ref = max(rec["v_surf"][-1], 0.3) if rec["v_surf"] else 1.0
                    if route is None:
                        self.ap.maj_waypoint(lat_e, lon_e)
                        la, lo = self.ap.cible_guidage(lat_e, lon_e, du_est, dv_est, v_ref, dt)
                        route = float(cap_initial(lat_e, lon_e, la, lo))
                    cap_cmd = cap_crabe_limite(route, v_ref, du_est, dv_est, nav.get("crabe_max_deg", 40.0))
                if est is not None and est.compas_hs and not gps_ok:
                    mode = "sans_cap"
                    cap_cmd = None
                if est is not None and largeur_km > nav["seuil_derive_km"] and est.compas_hs:
                    mode = "sans_cap"
                    cap_cmd = None

            # cap vrai effectivement tenu
            if cap_cmd is not None and gouvernable:
                if capt.compas.hs and not (est is not None and est.compas_hs):
                    # compas figé non détecté : l'autopilote « croit » tenir le cap -> le bateau tourne en rond
                    cap = float(self.aleas.rng("cercle").uniform(0, 2 * math.pi))
                elif est is not None and est.compas_hs:
                    cap = (cap_cmd + math.radians(self.aleas.rng("cog").normal(0, 10))) % (2 * math.pi)
                else:
                    cap = (cap_cmd - math.radians(capt.compas.biais_deg)) % (2 * math.pi)
            elif not gouvernable:
                cap = float(self.aleas.rng("cercle").uniform(0, 2 * math.pi))
            elif mode == "gel" and s["cap_gel"] is not None:
                cap = s["cap_gel"]

            # ---------------------------------------------------------------- puissance moteur
            if self.modules["energie"]:
                soc = bat.soc
                if mode in ("epave", "black-out", "veille", "bug_moteur", "sans_cap") or s["moteur_hs"] or s["chavire"]:
                    p_mot = 0.0
                elif mode == "gel":
                    p_mot = s["p_moteur_gel"]
                elif not gouvernable:
                    # sans gouverne : S10 coupe le moteur ; sans S10 le moteur tourne en rond
                    p_mot = 0.0 if self.sol("S10") != "absente" else gest.p_moteur(soc, hotel, 1.0, p_pv)
                else:
                    p_mot = gest.p_moteur(soc, hotel, fraction, p_pv)
                if gest.delestage >= 2 and mode not in ("gel",):
                    p_mot = 0.0
            else:
                p_mot = 0.0 if (self.epave or s["moteur_hs"] or s["chavire"]) else self.p_constante * fraction
            if s["calc"] == "ok":
                s["p_moteur_gel"], s["cap_gel"] = p_mot, cap

            # ---------------------------------------------------------------- bilan électrique
            soc_pct = 100.0
            if self.modules["energie"]:
                t_env = e["sst"] + cfg["bateau"]["batterie"]["delta_t_sur_mer_c"]
                surplus = p_pv - hotel - p_mot
                p_heat = EN.puissance_chauffage(cfg, bat, t_env, surplus) if s["calc"] != "eteint" else 0.0
                net = p_pv - hotel - p_mot - p_heat
                interdire_froid = self.sol("S6") != "absente"
                lim_av = bat.limite_charge_w(interdire_froid)
                p_abs, p_ecr, froid = bat.echanger(net, dt, interdire_froid)
                if net > 0 and p_ecr > 0 and lim_av < net:
                    stats["e_froid_bloquee"] += p_ecr * dt / 3600.0
                if froid:
                    wh = p_abs * dt / 3600.0
                    stats["wh_charge_froid"] += wh
                    if R is not None:
                        deg = R.reg["problemes"]["P11"]["degradation_charge_froid_par_wh"]
                        bat.facteur_sante = max(0.05, bat.facteur_sante - wh * deg)
                bat.thermique(t_env, p_heat, cfg["bateau"]["batterie"]["chauffage"]["conductance_w_par_k"], dt)
                stats["e_solaire"] += p_pv * dt / 3600.0
                stats["e_moteur"] += p_mot * dt / 3600.0
                stats["e_hotel"] += hotel * dt / 3600.0
                stats["e_chauffage"] += p_heat * dt / 3600.0
                stats["e_ecretee"] += p_ecr * dt / 3600.0
                if bat.bms_coupe and s["calc"] != "eteint":
                    s["calc"] = "eteint"
                    stats["blackouts"] += 1
                    if R is not None:
                        R.noter("P12", t)
                    self._ev("blackout", f"Batterie vide : le BMS coupe tout (black-out n°{stats['blackouts']}, "
                             f"SOC accessible 0 %, batterie {bat.t_c:.1f} °C)", "P12", 2)
                    if s["calc"] == "eteint":
                        p_mot = 0.0
                if s["calc"] == "eteint" and not self.epave:
                    if (bat.e_wh - bat.e_plancher()) / bat.cap_eff >= cfg["energie"]["soc_reconnexion_bms"]:
                        bat.bms_coupe = False
                        s["calc"] = "ok" if not s["gel_permanent"] else "gele"
                        s["redemarrages"] += 1
                        s["bug_cap"] = None
                        s["blocage_moteur"] = False
                        self._ev("redemarrage", f"Batterie rechargée : redémarrage du calculateur "
                                 f"(n°{s['redemarrages']})", "P12", 1)
                soc_pct = 100 * bat.soc

            # ---------------------------------------------------------------- physique
            p_prop = p_mot
            if s["helice"]:
                p_prop *= 0.3
            if s["barre"] == "secours":
                p_prop *= 0.85
            f_lacet = 1.0
            if R is not None and not self.epave:
                if p9["modele"] == "puissance":
                    # ancien modèle [H55] : perte appliquée à la puissance, à partir d'un seuil de 3 m
                    if e["hs"] > 3.0:
                        perte = R.param("P9", "perte_vitesse")
                        p_prop *= (1 - perte) ** 3
                        if perte > 0.05 and p_mot > 0 and "P9" not in R.occurrences:
                            R.noter("P9", t)
                            self._ev("P9", f"Mer forte (vagues {e['hs']:.1f} m) : le pilote louvoie (weaving), environ "
                                     f"{100 * perte:.0f} % de vitesse utile perdue tant que Hs > 3 m", "P9", 1)
                elif p_prop > 0 and gouvernable and cap_cmd is not None:
                    # modèle « lacet » [H72] : le bateau serpente autour de son cap (écart-type σ) ; la vitesse
                    # utile le long de la route vaut v·E[cos] = v·exp(−σ²/2). La résistance ajoutée par les
                    # vagues, elle, est dans B.equilibre : les deux effets ne se recouvrent pas.
                    sig = p9_sigma * min(1.0, e["hs"] / p9["hs_ref_m"])
                    if s["barre"] == "secours":
                        sig = math.hypot(sig, p9["lacet_secours_deg"])
                    f_lacet = RK_facteur_lacet(sig)
                    if 1 - f_lacet > 0.05 and "P9" not in R.occurrences:
                        R.noter("P9", t)
                        self._ev("P9", f"Mer forte (vagues {e['hs']:.1f} m) : la barre ne tient pas le cap, le "
                                 f"bateau fait des lacets de ±{sig:.0f}° (environ {100 * (1 - f_lacet):.0f} % de "
                                 f"route perdue)", "P9", 1)
            ux, uy, vu, vv = B.equilibre(self.coque, p_prop, cap, e["vent_u"], e["vent_v"], e["courant_u"],
                                         e["courant_v"], e["hs"], e["vague_dir_u"], e["vague_dir_v"], s["fouling"],
                                         cfg["bateau"]["aero"]["facteur_profil_vent"])
            if f_lacet < 1.0 and ux > 0:
                perdu = ux * (1.0 - f_lacet)
                ux -= perdu
                vu -= perdu * math.sin(cap)
                vv -= perdu * math.cos(cap)
            # exposition aux déferlantes : |sin| de l'angle entre l'axe du bateau et les vagues [H71]
            # (moteur coupé, le bateau est en travers au vent [H23])
            cap_eff = cap if p_prop > 0 else (math.atan2(e["vent_u"], e["vent_v"]) + math.pi / 2)
            n_vag = math.hypot(e["vague_dir_u"], e["vague_dir_v"])
            exposition = (abs(math.sin(cap_eff) * e["vague_dir_v"] - math.cos(cap_eff) * e["vague_dir_u"]) / n_vag
                          if n_vag > 1e-6 else 1.0)

            # ---------------------------------------------------------------- capteurs + estimateur
            lect = []
            if not self.epave:                 # épave : plus de capteurs à suivre, seul compte le devenir physique
                capt.pas(t, dt, lect)
            for typ, txt in lect:
                self._ev(typ, txt, "P18", 1)
                if R is not None and typ in ("gps_hs", "compas_hs", "compas_biais", "gps_coupure"):
                    f15 = R.param_solution("P15", "effet_capteurs", "S9")
                    if R.tirage("attribution_P15") < 1 - 1 / f15:
                        R.noter("P15", t)
            gps_dispo = capt.gps.disponible(t)
            if capt.gps.hs and est is not None and self.cause_fin is None and not self.epave and not balise:
                self.terminer("navigation", "Fin de mission : GPS définitivement hors service — l'arrivée ne pourra "
                              "pas être prouvée (règle D.1)", epave=False, pid=self._pid_courant or "P18")
            v_nom = self._v_nom(p_mot) if not s["chavire"] else 0.0
            cap_lu = None
            if est is not None:
                if not self.epave:
                    cap_lu = capt.cap_compas(math.degrees(cap)) if calc_actif else None
                    est.predire(t, dt, v_nom, cap_lu, endormi=s["calc"] in ("veille", "eteint") and
                                nav.get("derive_veille_max_ms", 2.5) > 0)
            # intégration de la vraie position
            lat2, lon2 = deplacer(self.lat, self.lon, vu * dt, vv * dt)
            dist_pas = haversine(self.lat, self.lon, lat2, lon2)
            if self.masque.au_large(self.lat, self.lon, lat2, lon2):
                touche = False                      # aucune terre à moins d'une maille : test exact inutile
            else:
                seg = LineString([(self.lon, self.lat), (lon2, lat2)])
                touche = self.terre_prep.intersects(seg)
            if not touche:
                self.lat, self.lon = lat2, lon2
                stats["dist_parcourue_nm"] += dist_pas / NM
            self.t = t + dt
            if est is not None and not self.epave:
                fix = None
                if calc_actif and gps_dispo:
                    x, y = est.enu.vers_local(self.lat, self.lon)
                    fix, saut = capt.fix_gps(self.t, float(x), float(y), dt)
                    if saut:
                        stats["sauts_gps"] += 1
                        stats.setdefault("sauts_t", []).append(self.t)
                r_corr = est.corriger(self.t, fix)
                for (tj, typ, txt) in est.journal:
                    self._ev(typ, txt, "P18", 0 if typ in ("fix_rejete", "reinit_boite") else 1, t=tj)
                est.journal.clear()
                if r_corr == "rejete":
                    stats["fix_rejetes"] += 1
                if not est.contient_geo(self.lat, self.lon):
                    # hypothèses de l'estimateur violées par un capteur en panne non (encore) détectée ?
                    hyp = (capt.compas.hs and not est.compas_hs) or abs(capt.compas.biais_deg) > (
                        nav["compas_demi_largeur_deg"] + (nav["compas_biais_max_deg"] if est.alerte_biais else 0))
                    stats["hors_boite_capteur" if hyp else "hors_boite"] = stats.get(
                        "hors_boite_capteur" if hyp else "hors_boite", 0) + 1
                    if not hyp:
                        stats["hors_boite_t"].append(self.t)
                # dérive estimée pour le crabe (dans le repère compas)
                du_est, dv_est = est.d_est
                if (not gps_dispo) and int(self.t // 3600) != int((self.t - dt) // 3600):
                    boites.append((self.t,) + est.boite_geo())
            else:
                du_est, dv_est = vu - ux * math.sin(cap), vv - ux * math.cos(cap)

            # ---------------------------------------------------------------- télémétrie / règlement
            if not self.epave or balise:
                peut = (s["calc"] in ("ok", "veille") and s["iridium"] and not s["chavire"]) or balise
                if peut and self.t - t_rapport >= cfg["bateau"]["iridium_periode_h"] * 3600.0:
                    t_rapport = self.t
                    stats["rapports"] += 1
                elif not peut:
                    silence_cumul += dt / 86400.0
                    if self._silence_pid is None or self.t - t_rapport < dt * 1.5:
                        self._silence_pid = ("P12" if s["calc"] == "eteint" else "P2" if s["chavire"] else
                                             "P20" if not s["iridium"] else "P17")
                if not disq and ((self.t - t_rapport) / 86400.0 > 10 or silence_cumul > 15):
                    disq = True
                    self._ev("disqualification", "Disqualifié : plus de 10 jours consécutifs (ou 15 cumulés) "
                             "sans position transmise (règle B1)", "P20", 2)
                    if self.cause_fin is None:
                        self.terminer("disqualification", "Fin de mission : disqualification pour silence radio",
                                      epave=False, pid=self._silence_pid)

            # ---------------------------------------------------------------- risques P1–P28
            if R is not None:
                ctx = dict(hs=e["hs"], tp=e["tp"], exposition=exposition, p_moteur=p_mot, peche=peche, commerce=self.densites.commerce_h_km2(self.lat, self.lon, t),
                           barre_active=gouvernable and cap_cmd is not None, jours=jours, redemarrages=s["redemarrages"],
                           calculateur_actif=calc_actif, en_mer=True, failsafe_retour=not s["iridium"])
                for pid, origine in R.pas(t, dt, ctx):
                    self._appliquer(pid, origine, s, bat, capt, est, R)
                # biofouling (P25) et drains d'ailes
                croissance = R.param_solution("P25", "croissance", "S17")
                s["fouling"] = B.encrassement(e["sst"], cfg, s["fouling"], dt / 86400.0 * croissance)
                if not s["drains"] and s["fouling"] >= R.reg["problemes"]["P25"]["seuil_drains"]:
                    s["drains"] = True
                    R.occurrences["P25"] = R.occurrences.get("P25", 0) + 1
                    R.premiere.setdefault("P25", t)
                    self._ev("P25", "L'encrassement bouche les trous de vidange des ailes : "
                             "l'auto-redressement n'est plus garanti", "P25", 1)
                # bug temporel à 49,7 jours (débordement de millis())
                if not bug49_fait and self.t >= t_bug49 and s["calc"] == "ok":
                    bug49_fait = True
                    if R.tirage("bug49") < R.param_solution("P17", "bug_49j", "S10") * (1.0 if self.sol("S13") != "validee" else 0.0):
                        R.occurrences["P17"] = R.occurrences.get("P17", 0) + 1
                        R.premiere.setdefault("P17", t)
                        self._gel(s, R, "débordement du compteur millis() au 49,7e jour")
                # chaviré : redressement tardif ; fin si > 3 jours à l'envers
                if s["chavire"]:
                    if self.aleas.evenement("redressement_tardif", R.reg["problemes"]["P2"]["redressement_tardif_par_jour"], dt):
                        s["chavire"] = False
                        self._ev("redressement", "Une vague remet le bateau à l'endroit", "P2", 1)
                    elif self.t - s["t_chavire"] > 3 * 86400 and self.cause_fin is None:
                        self.terminer("chavire", "Fin de mission : le bateau reste chaviré (panneaux et antennes "
                                      "sous l'eau)")
                # hélice engagée : dégagement spontané
                if s["helice"] and self.aleas.evenement("degagement", R.reg["problemes"]["P6"]["degagement_par_jour"], dt):
                    s["helice"] = False
                    self._ev("helice_libre", "L'hélice se dégage", "P6", 0)
                # énergie : production nulle et batterie vide -> mort
                if (self.modules["energie"] and s["circuits_ok"] == 0 and s["calc"] == "eteint"
                        and self.cause_fin is None):
                    self.terminer("panne_energie", "Fin de mission : plus aucune production solaire, batterie vide")
            else:
                s["fouling"] = B.encrassement(e["sst"], cfg, s["fouling"], dt / 86400.0)
            if self.icebergs is not None and "_issue" not in s:
                lam = self.icebergs.taux_collision_par_jour(t, self.lat, self.lon, math.hypot(vu, vv))
                if lam > 0 and self.aleas.evenement("iceberg", lam, dt):
                    self._choc_iceberg(s, R)
            if self.modules["energie"] and s["calc"] == "eteint" and self.cause_fin is None and not self.epave:
                # black-out prolongé (> 20 jours) : mission considérée perdue
                if self.t - self._t_dernier_on(rec) > 20 * 86400:
                    self.terminer("panne_energie", "Fin de mission : black-out de plus de 20 jours",
                                  pid="P12" if s["circuits_ok"] > 0 else "P10")

            # ---------------------------------------------------------------- enregistrement
            dist = haversine(self.lat, self.lon, arr["lat"], arr["lon"])
            if not traj_complete and (self.enregistrer_tout or int(self.t // 3600) != int((self.t - dt) // 3600)):
                vals = dict(t=self.t, lat=self.lat, lon=self.lon, v_surf=ux, dist_restante_nm=dist / NM, mode=mode)
                for k in keys:
                    rec[k].append(vals[k])
            elif self.enregistrer_tout or int(self.t // 3600) != int((self.t - dt) // 3600):
                vals = dict(t=self.t, lat=self.lat, lon=self.lon, cap=math.degrees(cap) % 360, v_surf=ux,
                            v_fond=math.hypot(vu, vv), p_moteur=p_mot, p_solaire=p_pv, p_chauffage=p_heat,
                            soc_pct=soc_pct, t_bat=bat.t_c, dist_restante_nm=dist / NM, encrassement=s["fouling"],
                            vent=math.hypot(e["vent_u"], e["vent_v"]), rafales=e["rafales"], hs=e["hs"],
                            courant=math.hypot(e["courant_u"], e["courant_v"]), sst=e["sst"], t_air=e["t_air"],
                            ghi=e["ghi"], estime_lat=lat_e, estime_lon=lon_e, boite_km=largeur_km,
                            contient=(est.contient_geo(self.lat, self.lon) if (est is not None and not self.epave)
                                      else True),
                            gps=gps_dispo, mode=mode, peche=peche)
                for k in keys:
                    rec[k].append(vals[k])

            # ---------------------------------------------------------------- fins physiques
            if touche:
                inter = seg.intersection(self.terre)
                p = inter.representative_point() if not inter.is_empty else seg.interpolate(1, normalized=True)
                self.lat, self.lon = p.y, p.x
                issue_phys = "echouement"
                self._ev("echouement", f"Échouement à la côte par {p.y:.2f}°N {abs(p.x):.2f}°W", None, 3)
                if self.cause_fin is None:
                    self.terminer("echouement", "Fin de mission : échouement avant la ligne d'arrivée")
                break
            if self.cause_fin is None and dist <= rayon and not self.epave:
                if est is None or capt.gps.disponible(self.t) or balise:
                    self.terminer("arrivee", f"Arrivée : entrée dans le cercle de 25 km ({dist / 1000:.1f} km du "
                                  f"centre), position {'GPS' if (est is None or capt.gps.disponible(self.t)) else 'de la balise S18'} "
                                  f"enregistrée — traversée réussie", epave=False)
                    issue_phys = "arrivee"
                    self.evts[-1].type = "arrivee"
                    break
                elif not getattr(self, "_signale_arrivee_sans_gps", False):
                    self._signale_arrivee_sans_gps = True
                    self._ev("arrivee_non_prouvee", "Le bateau traverse le cercle d'arrivée mais sans GPS : "
                             "aucune position ne le prouve (arrivée non homologuée)", "P18", 2)
            if self.issue_physique_finale(s):
                issue_phys = s["_issue"]
                break
            if self.t + dt > t_max:
                if self.cause_fin is None:
                    self.terminer("fin_donnees", "Fin de la période simulée : toujours en mer", epave=False)
                issue_phys = issue_phys or ("en_mer" if not self.epave else "derive")
                break
            if self.env.hors_domaine(self.lat, self.lon):
                if self.cause_fin is None:
                    self.terminer("hors_domaine", "Sortie de la zone de données (simulation arrêtée)", epave=False)
                issue_phys = "hors_domaine"
                break

        if self.cause_fin in (None,):
            self.cause_fin = "fin_donnees"
            self.t_fin_mission = self.t
        # position finale connue ?
        retrouve = issue_phys in ("arrivee", "capture", "echouement") or balise or \
            (s["iridium"] and s["calc"] in ("ok", "veille") and not s["chavire"])
        if not retrouve and R is not None:
            R.noter("P27", self.t)
            if hasattr(self, "_occ_mission"):
                self._occ_mission["P27"] = 1
                self._prem_mission.setdefault("P27", self.t)
        traj = {k: np.asarray(v) for k, v in rec.items()}
        stats["balise"] = balise
        stats["redemarrages"] = s["redemarrages"]
        stats["boites"] = boites
        stats["sante_batterie"] = bat.facteur_sante
        stats["fouling_final"] = s["fouling"]
        if est is not None:
            stats["fix_acceptes"] = est.n_acceptes
        stats["cause_pid"] = self.cause_pid
        return Resultat(traj=traj, evenements=self.evts, fin=self.cause_fin, t_fin=self.t_fin_mission,
                        issue_physique=issue_phys or "", t_fin_physique=self.t, retrouve=bool(retrouve),
                        occurrences=getattr(self, "_occ_mission", dict(R.occurrences) if R else {}),
                        premiere=getattr(self, "_prem_mission", dict(R.premiere) if R else {}),
                        stats=stats, graine=self.graine, jeu=(R.jeu.indice if R else 0),
                        solutions=dict(self.cfg["solutions"]),
                        config_resume=dict(p_constante=None if self.modules["energie"] else self.p_constante,
                                           start=cfg["mission"]["start"], modules=dict(self.modules),
                                           chauffage=cfg["bateau"]["batterie"]["chauffage"]["active"]))

    # ==================================================================
    def _t_dernier_on(self, rec):
        modes = rec["mode"]
        for i in range(len(modes) - 1, -1, -1):
            if modes[i] != "black-out":
                return rec["t"][i]
        return self.t0

    def _v_nom(self, p):
        """Vitesse eau calme pour la puissance p (inversion de la polaire, sans vent ni vagues)."""
        if p <= 0:
            return 0.0
        cache = getattr(self, "_polaire", None)
        if cache is None:
            V = np.linspace(0.0, 3.0, 301)
            P = np.array([self.coque.p_pour_vitesse_calme(v) for v in V])
            self._polaire = cache = (P, V)
        return float(np.interp(p, cache[0], cache[1]))

    def issue_physique_finale(self, s):
        return "_issue" in s

    def _fin_physique(self, s, issue, texte, cause):
        s["_issue"] = issue
        self._ev(issue, texte, None, 3)
        if self.cause_fin is None:
            self.terminer(cause, "Fin de mission : " + texte[0].lower() + texte[1:])

    def _gel(self, s, R, raison):
        reprise = R.tirage("watchdog") < R.param_solution("P17", "watchdog_reprise", "S11")
        if reprise:
            s["redemarrages"] += 1
            self._ev("gel_reprise", f"Le calculateur se fige ({raison}) ; le watchdog le redémarre", "P17", 1)
            s["bug_cap"] = None
            s["blocage_moteur"] = False
        else:
            s["calc"] = "gele"
            s["gel_permanent"] = True
            self._ev("gel", f"Le calculateur se fige ({raison}) et rien ne le redémarre : moteur et barre figés",
                     "P17", 2)
            self.terminer("calculateur", "Fin de mission : calculateur figé", epave=False)

    def _appliquer(self, pid, origine, s, bat, capt, est, R):
        """Conséquence d'un problème (transition d'état), puis cascades."""
        P = R.reg["problemes"][pid]
        c = P["consequence"]
        titre = P["titre"]
        self._pid_courant = pid
        if self.epave and c not in ("rencontre_peche", "naufrage", "collision"):
            return
        orig = "" if origine == "spontané" else f" ({origine})"
        if c == "voie_eau" or c == "voie_eau_lente":
            s["voie_eau"] += 1.0 if c == "voie_eau" else 0.3
            self._ev(pid, f"{titre} : voie d'eau{' importante' if c == 'voie_eau' else ' lente'}{orig}", pid, 2)
        elif c == "chavirage":
            p_red = R.proba_redressement(s["drains"])
            if R.tirage("redressement") < p_red:
                self._ev(pid, f"Chavirage par mer forte ; le bateau se redresse "
                         f"({'ailes inondables' if self.sol('S1') != 'absente' else 'par chance'})", pid, 1)
            else:
                s["chavire"] = True
                s["t_chavire"] = self.t
                self._ev(pid, "Chavirage : le bateau reste à l'envers (panneaux et antennes sous l'eau)", pid, 2)
        elif c == "panne_moteur":
            s["moteur_hs"] = True
            self._ev(pid, f"{titre} : le moteur tombe en panne{orig}", pid, 2)
            self.terminer("sans_propulsion", "Fin de mission : plus de propulsion")
        elif c == "helice_engagee":
            s["helice"] = True
            self._ev(pid, f"{titre} : hélice engagée par un débris (puissance utile −70 %)", pid, 1)
        elif c == "barre_bloquee":
            s["barre"] = "bloquee"
            self._ev(pid, f"{titre} : l'actionneur de barre casse, safran bloqué{orig}", pid, 2)
        elif c == "secours_gouverne":
            if s["barre"] != "bloquee":
                return
            if R.tirage("secours_gouverne") < R.param("P8", "secours"):
                s["barre"] = "secours"
                self._ev(pid, "Redondance de gouverne : la poussée différentielle / le 2e safran prend le relais",
                         pid, 1)
            else:
                self._ev(pid, "Aucune redondance de gouverne : le bateau ne peut plus tenir de cap", pid, 2)
                self.terminer("sans_gouverne", "Fin de mission : plus de gouverne")
        elif c == "perte_circuit_pv":
            if s["circuits_ok"] > 0:
                s["circuits_ok"] -= 1
                reste = s["circuits_ok"]
                self._ev(pid, f"{titre} : un circuit solaire/MPPT tombe en panne (reste {reste}/{s['circuits']})",
                         pid, 2 if reste == 0 else 1)
        elif c == "perte_capacite":
            bat.facteur_sante *= 0.5 if self.sol("S6") != "absente" else 0.05
            bat.e_wh = min(bat.e_wh, bat.cap_eff)
            self._ev(pid, f"{titre} : défaillance de cellule, capacité ramenée à {100 * bat.facteur_sante:.0f} %",
                     pid, 2)
        elif c == "panne_electronique":
            cibles = ["gps", "compas", "iridium", "calculateur", "moteur", "ais"]
            k = int(R.tirage(f"elec:{pid}") * len(cibles))
            cible = cibles[min(k, len(cibles) - 1)]
            noms = dict(gps="le GPS", compas="le compas", iridium="le modem Iridium", calculateur="le calculateur",
                        moteur="le contrôleur moteur", ais="l'AIS/feu")
            self._ev(pid, f"{titre} : panne de {noms[cible]}{orig}", pid, 2)
            if cible == "gps":
                capt.gps.hs = True
            elif cible == "compas":
                capt.compas.hs = True
                capt.compas.valeur_gelee = float(R.tirage("compas_gele") * 360)
            elif cible == "iridium":
                s["iridium"] = False
            elif cible == "calculateur":
                self._gel(s, R, "court-circuit / corrosion")
            elif cible == "moteur":
                s["moteur_hs"] = True
                self.terminer("sans_propulsion", "Fin de mission : contrôleur moteur hors service")
        elif c == "bug_logique":
            iss = P["issues"]
            u = R.tirage("bug_logique")
            if u < iss["cap_errone"]:
                s["bug_cap"] = float(R.tirage("bug_cap") * 2 * math.pi)
                s["t_bug"] = self.t
                self._ev(pid, f"{titre} : une condition jamais prévue fait tenir au bateau un cap erroné "
                         f"({math.degrees(s['bug_cap']):.0f}°) jusqu'au prochain redémarrage", pid, 2)
            elif u < iss["cap_errone"] + iss["blocage_moteur"]:
                s["blocage_moteur"] = True
                s["t_bug"] = self.t
                self._ev(pid, f"{titre} : le logiciel reste bloqué dans un mode moteur arrêté", pid, 2)
            else:
                self._gel(s, R, "événement imprévu")
        elif c == "gel_calculateur":
            if origine.startswith("cascade P20"):
                if R.tirage("failsafe") < R.param_solution("P17", "failsafe_retour", "S10"):
                    s["failsafe"] = True
                    s["t_failsafe"] = self.t
                    self._ev(pid, "Failsafe dangereux : après 48 h sans télémétrie, le logiciel décide de "
                             "« revenir au point de départ » (cas SB Wave)", pid, 2)
                return
            self._gel(s, R, "bug temporel / saturation")
        elif c == "panne_capteur_nav":
            if R.tirage("p18_cible") < 0.5:
                capt.gps.hs = True
                self._ev(pid, f"{titre} : le GPS ne fournit plus de position", pid, 2)
            else:
                capt.compas.hs = True
                capt.compas.valeur_gelee = float(R.tirage("compas_gele") * 360)
                self._ev(pid, f"{titre} : le compas se fige", pid, 2)
        elif c == "perte_iridium":
            if s["iridium"]:
                s["iridium"] = False
                self._ev(pid, f"{titre} : le modem Iridium ne transmet plus", pid, 2)
        elif c == "perte_reception":
            if s["reception"]:
                s["reception"] = False
                self._ev(pid, f"{titre} : plus de réception de données (sans effet sur la route : pas de "
                         f"routage météo dans ce modèle)", pid, 0)
        elif c == "collision":
            g = P["gravite"]
            u = R.tirage("collision")
            if u < g["coule"]:
                self._ev(pid, "Collision avec un navire de commerce : le bateau est détruit", pid, 3)
                self._fin_physique(s, "coule", "Coulé après une collision", "coule")
            elif u < g["coule"] + g["voie_eau"]:
                s["voie_eau"] += 1.0
                self._ev(pid, "Collision avec un navire : coque endommagée, voie d'eau", pid, 2)
                from .risks import Cascade
                R.cascades.append(Cascade(self.t + 3600, "P13", "cascade P22"))
            else:
                self._ev(pid, "Frôlé par un navire : sans dégât", pid, 0)
        elif c == "rencontre_peche":
            self._rencontre_peche(s, R, pid)
        elif c == "morsure":
            self._ev(pid, "Faune : morsure / choc d'un animal marin sur la coque", pid, 1)
        elif c == "naufrage":
            if R.tirage("naufrage") < R.param("P28", "coule"):
                self._fin_physique(s, "coule", "Le bateau coule (voie d'eau, flottabilité insuffisante)", "coule")
            else:
                self._ev(pid, "Voie d'eau, mais la flottabilité (âme mousse) maintient le bateau à flot", pid, 1)
        R.programmer_cascades(self.t, pid)
        self._pid_courant = None

    def _choc_iceberg(self, s, R):
        """Choc avec un iceberg (module facultatif, hors P1–P28) [H77]."""
        g = self.icebergs.gravite
        u = float(self.aleas.rng("iceberg").random())
        self._pid_courant = "iceberg"
        if u < g["coule"]:
            self._ev("iceberg", "Choc avec un iceberg : la coque est détruite", "iceberg", 3)
            self._fin_physique(s, "coule", "Coulé après un choc avec un iceberg", "coule")
        elif u < g["coule"] + g["voie_eau"]:
            s["voie_eau"] += 1.0
            self._ev("iceberg", "Choc avec un iceberg : coque endommagée, voie d'eau", "iceberg", 2)
            if R is not None:
                from .risks import Cascade
                R.cascades.append(Cascade(self.t + 3600, "P28", "cascade iceberg"))
        else:
            self._ev("iceberg", "Le bateau heurte un glaçon (growler) sans dégât", "iceberg", 0)
        self._pid_courant = None

    def _cause_par_defaut(self, cause):
        return {"panne_energie": "P10", "disqualification": self._silence_pid or "P20",
                "fin_donnees": "lenteur", "hors_domaine": "lenteur", "echouement": "P18", "arrivee": None,
                "chavire": "P2", "calculateur": "P17"}.get(cause)

    def _rencontre_peche(self, s, R, pid):
        P = R.reg["problemes"]["P24"]
        iss = P["issues"]
        m_eng = R.jeu.mult[("P24", "S1", self.sol("S1"))] * R.jeu.mult[("P24", "S16", self.sol("S16"))] * \
            R.jeu.mult[("P24", "S4", self.sol("S4"))]
        p_eng = min(0.9, iss["engagement"] * m_eng)
        p_rec = iss["recupere"]
        u = R.tirage("rencontre")
        if u < p_eng:
            v = R.tirage("engagement")
            ei = P["engagement_issue"]
            if v < ei["libere"]:
                self._ev(pid, "Pris dans un engin de pêche, le bateau finit par se libérer", pid, 1)
            elif v < ei["libere"] + ei["capture"]:
                self._fin_physique(s, "capture", "Pris dans un filet / une palangre et remonté à bord par le "
                                   "pêcheur", "capture")
            else:
                self._fin_physique(s, "perdu_filet", "Pris dans un engin de pêche et entraîné : perdu",
                                   "perdu_filet")
        elif u < p_eng + p_rec:
            laisse = R.param_solution("P23", "laisse", "S15")
            if R.tirage("laisse") < laisse:
                self._ev("P23", "Un pêcheur s'approche, identifie un drone de course (marquage, AIS) et le laisse "
                         "continuer", "P23", 1)
                R.occurrences["P23"] = R.occurrences.get("P23", 0) + 1
                R.premiere.setdefault("P23", self.t)
            else:
                self._fin_physique(s, "capture", "Un pêcheur repère le bateau et le récupère à bord", "capture")
        else:
            self._ev(pid, "Croise un navire de pêche, sans suite", pid, 0)


def cap_crabe_limite(route, v, du, dv, crabe_max_deg):
    cap = cap_crabe(route, v, du, dv)
    ecart = (cap - route + math.pi) % (2 * math.pi) - math.pi
    lim = math.radians(crabe_max_deg)
    if abs(ecart) > lim:
        cap = (route + math.copysign(lim, ecart)) % (2 * math.pi)
    return cap
