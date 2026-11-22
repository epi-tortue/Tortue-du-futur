"""Localisation ensembliste garantie avec Codac v2.

État : boîte de position [p] (IntervalVector 2D) en coordonnées locales ENU (mètres),
recentrée tous les `recentrage_km` (30 km par défaut).

Prédiction (CtcInverse) sur l'équation d'évolution (repère : x = est, y = nord, ψ = cap vrai
compté depuis le nord dans le sens horaire) :

    p(k+1) = p(k) + dt · ( v · [sin ψ, cos ψ] + d )

    v ∈ v_nom(P) · [1 − ε, 1 + ε]     v_nom : vitesse eau calme du modèle de coque pour la
                                        puissance appliquée [H30]
    ψ ∈ cap_compas ± w                 w = 3σ + déclinaison résiduelle (+ biais max si alerte)
    d ∈ d̂ ± δ(t)                       « dérive » = tout ce que le modèle ne voit pas : courant,
                                        fardage, ralentissement par vent/vagues, biais compas
                                        lent. d̂ est estimée sur une fenêtre glissante de fix GPS
                                        acceptés (longue base) ; δ grandit avec le temps écoulé
                                        depuis le dernier fix [H31].

Correction : [p] ← [p] ∩ [fix ± r_gps]. Intersection vide ⇒ fix rejeté (GPS corrompu).
Contrôle du compas : cap déduit de deux fix distants d'au moins 1 h (longue base) comparé au
cap compas moyen ; N incohérences consécutives ⇒ alerte biais (bornes élargies), puis compas
déclaré HS si l'incohérence persiste.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np
from codac import AnalyticFunction, CtcInverse, Interval, IntervalVector, VectorVar, cos, sin, vec

from . import arrondi as AR
from .geo import ENU

# `import codac` laisse le processeur en arrondi vers le haut : on revient au plus proche pour le reste du
# simulateur, et on ne repasse vers le haut que pendant les calculs Codac (sim/arrondi.py) [H78].
AR.au_plus_proche()


def _fonction_evolution():
    x = VectorVar(9)   # p0x p0y p1x p1y v psi dx dy dt
    f = AnalyticFunction([x], vec(
        x[2] - x[0] - x[8] * (x[4] * sin(x[5]) + x[6]),
        x[3] - x[1] - x[8] * (x[4] * cos(x[5]) + x[7])))
    return CtcInverse(f, IntervalVector([[0, 0], [0, 0]]))


_CTC = None


def _ctc():
    global _CTC
    if _CTC is None:
        with AR.vers_le_haut():
            _CTC = _fonction_evolution()
    return _CTC


def _ang_moyen_deg(liste):
    s = sum(math.sin(math.radians(a)) for a in liste)
    c = sum(math.cos(math.radians(a)) for a in liste)
    return math.degrees(math.atan2(s, c)) % 360.0


def _ecart_ang(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


class EstimateurCodac:
    def __init__(self, cfg: dict, lat0: float, lon0: float, t0: float):
        self.n = cfg["navigation"]
        self.enu = ENU(lat0, lon0)
        r = self.n["gps_demi_largeur_m"]
        self.box = IntervalVector([[-r, r], [-r, r]])
        self.d_est = np.zeros(2)
        self.t_fix = t0
        self.S = np.zeros(2)                       # intégrale de v_nom · cap compas
        self.fixes = deque()                       # (t, x, y, Sx, Sy, d_est)
        self.compas_lectures = deque()             # (t, cap)
        self.alerte_biais = False
        self.compas_hs = False
        self.incoherences = 0
        self.coherences = 0
        self.n_rejets = 0
        self.n_acceptes = 0
        self.n_reinit = 0
        self.derive_connue = False
        self.rejet_prec = None                     # dernier fix rejeté (t, x, y)
        self.v_hist = deque()                      # (t, v_nom) sur la fenêtre de dérive
        self.journal: list[tuple[float, str, str]] = []
        self.recentrage_m = self.n.get("recentrage_km", 30.0) * 1000.0

    # ------------------------------------------------------------------
    # La boîte est gardée sous forme de 4 bornes flottantes (_lim) : lire une borne d'un IntervalVector
    # coûte un appel C++ (~2 µs), et on les lit plusieurs fois par pas. L'objet Codac n'est reconstruit
    # que s'il sert (intersection), et le centre et la largeur sont calculés par Codac, une fois par
    # boîte (Interval.mid() n'est pas toujours (lb + ub) / 2) : résultats identiques au bit près.
    @property
    def box(self) -> IntervalVector:
        b = self._box
        if b is None:
            x0, x1, y0, y1 = self._lim
            b = self._box = IntervalVector([[x0, x1], [y0, y1]])
        return b

    @box.setter
    def box(self, b: IntervalVector):
        self._box = b
        self._lim = (b[0].lb(), b[0].ub(), b[1].lb(), b[1].ub())
        self._mid = self._larg = None

    def _poser(self, x0, x1, y0, y1):
        """Nouvelle boîte [x0, x1] × [y0, y1] (bornes non vides), sans objet Codac intermédiaire."""
        self._lim = (x0, x1, y0, y1)
        self._box = self._mid = self._larg = None

    def largeur_m(self) -> float:
        if self._larg is None:
            x0, x1, y0, y1 = self._lim
            AR.haut()
            try:
                self._larg = float(max(Interval(x0, x1).diam(), Interval(y0, y1).diam()))
            finally:
                AR.au_plus_proche()
        return self._larg

    def centre_local(self):
        if self._mid is None:
            x0, x1, y0, y1 = self._lim
            AR.haut()
            try:
                self._mid = (float(Interval(x0, x1).mid()), float(Interval(y0, y1).mid()))
            finally:
                AR.au_plus_proche()
        return self._mid

    def centre_geo(self):
        x, y = self.centre_local()
        la, lo = self.enu.vers_geo(x, y)
        return float(la), float(lo)

    def contient_geo(self, lat, lon, tol_m=1e-6) -> bool:
        x, y = self.enu.vers_local(lat, lon)
        x0, x1, y0, y1 = self._lim
        return x0 - tol_m <= x <= x1 + tol_m and y0 - tol_m <= y <= y1 + tol_m

    def boite_geo(self):
        """(lat_min, lat_max, lon_min, lon_max) pour l'affichage."""
        x0, x1, y0, y1 = self._lim
        la0, lo0 = self.enu.vers_geo(x0, y0)
        la1, lo1 = self.enu.vers_geo(x1, y1)
        return float(la0), float(la1), float(lo0), float(lo1)

    def delta(self, t, v_nom=None, cap_deg=None):
        """Demi-largeur de la borne de dérive.

        + changement de régime : la dérive estimée inclut le ralentissement (vent, vagues) qui est
          proportionnel à la vitesse commandée, et l'attitude change quand le moteur s'arrête
          (le bateau se met en travers) -> on ajoute |v_nom − v_nom moyen de la fenêtre| et
          `derive_marge_regime_ms` si le moteur passe de marche à arrêt (ou l'inverse)."""
        if not self.derive_connue:
            return self.n["derive_marge_max_ms"]
        h = max(0.0, t - self.t_fix) / 3600.0
        d = self.n["derive_marge_ms"] + self.n["derive_croissance_ms_par_h"] * h
        if v_nom is not None and self.v_hist:
            v_moy = sum(v for _, v in self.v_hist) / len(self.v_hist)
            d += abs(v_nom - v_moy)
            arret_moy = sum(1 for _, v in self.v_hist if v <= 0) / len(self.v_hist)
            if (v_nom <= 0 and arret_moy < 0.5) or (v_nom > 0 and arret_moy >= 0.5):
                d += self.n.get("derive_marge_regime_ms", 0.15)
        # la part de la dérive liée à l'axe du bateau (ralentissement, fardage latéral) tourne avec
        # lui : + vitesse de référence × changement de cap par rapport à la fenêtre
        caps = [c for (tc, c) in self.compas_lectures if tc >= t - self.n["derive_fenetre_h"] * 3600.0]
        if cap_deg is not None and caps:
            dpsi = abs(_ecart_ang(cap_deg, _ang_moyen_deg(caps)))
            v_ref = max(v_nom or 0.0, max((v for _, v in self.v_hist), default=0.0))
            d += v_ref * 2 * math.sin(math.radians(min(dpsi, 180.0)) / 2)
        return min(self.n["derive_marge_max_ms"], d)

    def demi_largeur_compas_deg(self):
        w = self.n["compas_demi_largeur_deg"]
        if self.alerte_biais:
            w += self.n["compas_biais_max_deg"]
        return w

    # ------------------------------------------------------------------
    def predire(self, t, dt, v_nom, cap_compas_deg, endormi=False):
        """Propage la boîte de t à t+dt. cap_compas_deg=None si aucun cap fiable.

        endormi=True : le calculateur ne tourne pas (veille de nuit, black-out). La dérive estimée moteur
        en marche ne vaut plus rien (le bateau s'est mis en travers) : la boîte grandit avec la seule
        borne physique de la dérive libre, ±derive_veille_max_ms autour de zéro [H31]."""
        if endormi:
            vmax = self.n.get("derive_veille_max_ms", 2.5)
            m = vmax * dt * 1.01 + 0.5
            x0, x1, y0, y1 = self._lim
            self._poser(x0 - m, x1 + m, y0 - m, y1 + m)
            self.derive_connue = False                 # à réestimer au réveil…
            self.d_est = np.zeros(2)                   # …en repartant de zéro (l'ancienne valeur est périmée)
            self.fixes.clear()
            self.v_hist.clear()
            self._recentrer()
            return
        eps = self.n["erreur_modele_vitesse_rel"]
        eps_bas = self.n.get("erreur_modele_vitesse_bas_rel", eps)
        v_lb, v_ub = max(0.0, v_nom * (1 - eps_bas)), v_nom * (1 + eps)   # bornes exactes de l'intervalle v
        dl = self.delta(t + dt, v_nom, None if self.compas_hs else cap_compas_deg)
        if cap_compas_deg is None or self.compas_hs:
            psi = [-math.pi, math.pi]
        else:
            w = math.radians(self.demi_largeur_compas_deg())
            c = math.radians(cap_compas_deg)
            psi = [c - w, c + w]
            self.S += dt * v_nom * np.array([math.sin(c), math.cos(c)])
            self.compas_lectures.append((t, cap_compas_deg))
        self.v_hist.append((t, v_nom))
        while self.v_hist and self.v_hist[0][0] < t - self.n["derive_fenetre_h"] * 3600.0:
            self.v_hist.popleft()
        x0, x1, y0, y1 = self._lim
        X = IntervalVector([
            [x0, x1], [y0, y1],
            [-1e9, 1e9], [-1e9, 1e9], [v_lb, v_ub], psi,
            [self.d_est[0] - dl, self.d_est[0] + dl], [self.d_est[1] - dl, self.d_est[1] + dl], [dt, dt]])
        ctc = _ctc()
        AR.haut()
        try:
            ctc.contract(X)
        finally:
            AR.au_plus_proche()
        if X.is_empty():   # ne devrait pas arriver (équation toujours satisfiable)
            raise RuntimeError("Contraction vide en prédiction")
        # marge de projection : l'ENU équirectangulaire déforme les distances de ≤ 0,5 %
        # à 30 km de l'origine ; on élargit de 1 % du déplacement maximal du pas.
        m = 0.01 * dt * (v_ub + math.hypot(abs(self.d_est[0]) + dl, abs(self.d_est[1]) + dl)) + 0.5
        X2, X3 = X[2], X[3]
        self._poser(X2.lb() - m, X2.ub() + m, X3.lb() - m, X3.ub() + m)
        while self.compas_lectures and self.compas_lectures[0][0] < t - 3 * 3600:
            self.compas_lectures.popleft()
        self._recentrer()

    def corriger(self, t, fix_local):
        """Retourne 'aucun' | 'accepte' | 'rejete'."""
        if fix_local is None:
            return "aucun"
        r = self.n["gps_demi_largeur_m"]
        fx, fy = fix_local
        # Intersection boîte ∩ [fix ± r] : max et min des bornes, sans arrondi (identique à IntervalVector &)
        b0, b1, c0, c1 = self._lim

        def inter(r):
            i = (max(b0, fx - r), min(b1, fx + r), max(c0, fy - r), min(c1, fy + r))
            return None if (i[0] > i[1] or i[2] > i[3]) else i
        res = inter(r)
        # Marge de saut [H34] : la détection d'un fix corrompu se fait avec la boîte GPS étroite (±r) ; un
        # fix accepté ne contracte la position qu'avec la boîte élargie (±(r + marge)). Un saut plus petit
        # que la marge, indétectable, ne fait donc plus sortir la vraie position de la boîte.
        marge = self.n.get("gps_marge_saut_m", 0.0)
        if marge > 0 and res is not None:
            r += marge
            res = inter(r)
        if res is None:
            self.n_rejets += 1
            cx, cy = self.centre_local()
            ecart = math.hypot(fx - cx, fy - cy)
            # Reprise garantie : deux fix rejetés consécutifs et cohérents entre eux -> soit la boîte
            # est fausse, soit le GPS l'est ; la vraie position est dans l'enveloppe des deux.
            if self.rejet_prec is not None:
                t0, x0, y0 = self.rejet_prec
                vmax = 4.0
                if math.hypot(fx - x0, fy - y0) <= vmax * (t - t0) + 2 * r:
                    b0, b1, c0, c1 = self._lim
                    self._poser(min(b0, fx - r), max(b1, fx + r), min(c0, fy - r), max(c1, fy + r))
                    self.n_reinit += 1
                    self.rejet_prec = None
                    self.journal.append((t, "reinit_boite", f"Deux fix GPS cohérents contredisent la boîte : "
                                         f"élargissement à l'enveloppe boîte ∪ GPS (écart {ecart:.0f} m)"))
                    return "reinit"
            self.rejet_prec = (t, fx, fy)
            self.journal.append((t, "fix_rejete", f"Fix GPS rejeté (incohérent avec la boîte, écart ≈ {ecart:.0f} m)"))
            return "rejete"
        self.rejet_prec = None
        self._poser(*res)
        self.n_acceptes += 1
        if t - self.t_fix > 3600.0:
            # retour du GPS après une coupure : la dérive estimée avant la coupure est périmée
            self.fixes.clear()
            self.derive_connue = False
        self._maj_derive(t, fx, fy)
        self._controle_compas(t, fx, fy)
        self.t_fix = t
        return "accepte"

    # ------------------------------------------------------------------
    def _maj_derive(self, t, fx, fy):
        W = self.n["derive_fenetre_h"] * 3600.0
        self.fixes.append((t, fx, fy, self.S[0], self.S[1], self.d_est.copy()))
        while len(self.fixes) > 2 and self.fixes[1][0] <= t - W:
            self.fixes.popleft()
        t0, x0, y0, sx0, sy0, _ = self.fixes[0]
        T = t - t0
        if T >= 1800.0:
            self.derive_connue = True
            self.d_est = np.array([(fx - x0 - (self.S[0] - sx0)) / T, (fy - y0 - (self.S[1] - sy0)) / T])

    def _controle_compas(self, t, fx, fy):
        if self.compas_hs:
            return
        # fix de référence ≥ 1 h avant
        ref = None
        for f in self.fixes:
            if t - f[0] >= 3600.0:
                ref = f
        if ref is None:
            return
        t0, x0, y0, sx0, sy0, d0 = ref
        T = t - t0
        lect = [c for (tc, c) in self.compas_lectures if t0 <= tc <= t]
        if len(lect) < 2:
            return
        v_moy = math.hypot(self.S[0] - sx0, self.S[1] - sy0) / T   # norme de la vitesse modèle moyenne
        if v_moy < 0.3:
            return
        r = self.n["gps_demi_largeur_m"] + self.n.get("gps_marge_saut_m", 0.0)
        dl = self.n["derive_marge_ms"] * 2
        # vitesse fond moyenne (boîte) moins la dérive -> vecteur v·h (boîte)
        hx = IntervalVector([[(fx - x0 - 2 * r) / T - d0[0] - dl, (fx - x0 + 2 * r) / T - d0[0] + dl]])[0]
        hy = IntervalVector([[(fy - y0 - 2 * r) / T - d0[1] - dl, (fy - y0 + 2 * r) / T - d0[1] + dl]])[0]
        if hx.contains(0.0) and hy.contains(0.0):
            return
        coins = [math.degrees(math.atan2(a, b)) % 360 for a in (hx.lb(), hx.ub()) for b in (hy.lb(), hy.ub())]
        c_moy = _ang_moyen_deg(coins)
        demi = max(abs(_ecart_ang(c, c_moy)) for c in coins)
        cap_c = _ang_moyen_deg(lect)
        incoherent = abs(_ecart_ang(cap_c, c_moy)) > demi + self.demi_largeur_compas_deg()
        N = self.n["compas_detection_n"]
        if incoherent:
            self.incoherences += 1
            self.coherences = 0
            if self.incoherences == N and not self.alerte_biais:
                self.alerte_biais = True
                self.journal.append((t, "alerte_compas", f"Alerte : cap compas incohérent avec la route GPS "
                                     f"(écart ≈ {abs(_ecart_ang(cap_c, c_moy)):.0f}°) — bornes de cap élargies"))
            elif self.incoherences >= 3 * N and self.alerte_biais:
                self.compas_hs = True
                self.journal.append((t, "compas_declare_hs", "Compas déclaré hors service par l'estimateur "
                                     "(navigation à la route fond GPS)"))
        else:
            self.coherences += 1
            self.incoherences = 0
            if self.alerte_biais and self.coherences >= 4 * N:
                self.alerte_biais = False
                self.journal.append((t, "fin_alerte_compas", "Compas de nouveau cohérent : bornes resserrées"))

    def _recentrer(self):
        x, y = self.centre_local()
        if math.hypot(x, y) < self.recentrage_m:
            return
        la, lo = self.enu.vers_geo(x, y)
        ancien = self.enu
        nouveau = ENU(float(la), float(lo))
        xs, ys = [], []
        b0, b1, c0, c1 = self._lim
        for bx in (b0, b1):
            for by in (c0, c1):
                a, b = ancien.vers_geo(bx, by)
                u, v = nouveau.vers_local(a, b)
                xs.append(float(u))
                ys.append(float(v))
        m = 1.0 + 1e-6 * self.largeur_m()     # marge de conversion (projection non conforme)
        self._poser(min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m)
        nf = deque()
        for (tf, fx, fy, sx, sy, d) in self.fixes:
            a, b = ancien.vers_geo(fx, fy)
            u, v = nouveau.vers_local(a, b)
            nf.append((tf, float(u), float(v), sx, sy, d))
        self.fixes = nf
        self.enu = nouveau
