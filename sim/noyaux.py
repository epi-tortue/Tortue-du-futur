"""Noyaux numériques compilés (numba), avec repli en Python pur.

Les fonctions ci-dessous reprennent EXACTEMENT les opérations flottantes de `boat.equilibre` et
`boat._resoudre_axe` (même ordre, mêmes fonctions de la bibliothèque C) : avec ou sans numba, le
résultat est identique au bit près. C'est indispensable, car la trajectoire est chaotique : le moindre
écart d'arrondi finit par changer l'issue d'une mission, et on ne pourrait plus comparer deux versions
du code sur les mêmes graines (test tests/test_non_regression.py).

Points d'attention pour l'égalité au bit près :
  - les puissances sont écrites avec un exposant flottant (x ** 4.0) : numba remplace x ** 4 (entier)
    par des multiplications, alors que Python appelle pow() ;
  - les constantes de la coque sont précalculées dans le même ordre d'opérations qu'en Python
    (multiplications de gauche à droite).

Désactivation : variable d'environnement EPITORTUE_SANS_NUMBA=1 ou config `simulation.numba: false`.
"""
from __future__ import annotations

import math
import os

import numpy as np

RHO = 1025.0
RHO_AIR = 1.225
NU = 1.19e-6
N_CELL = 8192
W_CELL = 9.0 / N_CELL

try:
    if os.environ.get("EPITORTUE_SANS_NUMBA"):
        raise ImportError
    from numba import njit
    NUMBA = True
except ImportError:                       # numba absent : mêmes fonctions, interprétées
    NUMBA = False

    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f


@njit(cache=True)
def _dl_mul(x, y):
    """Produit exact x·y = hi + lo (Dekker / Veltkamp, sans fma)."""
    hi = x * y
    c = 134217729.0                       # 2^27 + 1
    t = c * x
    xh = t - (t - x)
    xl = x - xh
    t = c * y
    yh = t - (t - y)
    yl = y - yh
    lo = ((xh * yh - hi) + xh * yl + xl * yh) + xl * yl
    return hi, lo


@njit(cache=True)
def hypot(a, b):
    """math.hypot de CPython ≥ 3.8 (vector_norm, mathmodule.c), et non hypot() de la bibliothèque C :
    les deux diffèrent parfois d'un bit."""
    a, b = abs(a), abs(b)
    if math.isnan(a) or math.isnan(b):
        if math.isinf(a) or math.isinf(b):
            return math.inf
        return math.nan
    mx = max(a, b)
    if math.isinf(mx):
        return mx
    if mx == 0.0:
        return mx
    _, max_e = math.frexp(mx)
    if max_e < -1023:                     # sous-normaux : hors du domaine du simulateur
        return math.hypot(a, b)
    scale = math.ldexp(1.0, -max_e)
    csum, frac1, frac2 = 1.0, 0.0, 0.0
    for x in (a, b):
        x *= scale
        ph, pl = _dl_mul(x, x)
        sh = csum + ph
        sl = ph - (sh - csum)
        csum = sh
        frac1 += pl
        frac2 += sl
    h = math.sqrt(csum - 1.0 + (frac1 + frac2))
    ph, pl = _dl_mul(-h, h)
    sh = csum + ph
    sl = ph - (sh - csum)
    csum = sh
    frac1 += pl
    frac2 += sl
    x = csum - 1.0 + (frac1 + frac2)
    h += x / (2.0 * h)
    return h / scale


@njit(cache=True)
def _f_axe(u, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v, r_h, mgr, un_k, un_e):
    if u > 1e-3:
        t = min(etap / u, t_stat) if p > 0 else 0.0
    else:
        t = t0
    va = abs(u)
    if va < 1e-9:
        rc = 0.0
    else:
        re = max(va * lwl / NU, 1e5)
        cf = 0.075 / (math.log10(re) - 2.0) ** 2.0
        rf = c_rf * va * va * cf * un_e
        fnv = va / den_fn
        x = c_v * fnv ** 4.0 / r_h
        rc = math.copysign(un_k * rf + mgr * x / (1.0 + x), u)
    return t + f_air_x - rc - r_vagues * math.tanh(u / 0.2)


@njit(cache=True)
def resoudre_axe(p, f_air_x, r_vagues, encr, k_prec, lwl, c_rf, den_fn, c_v, r_h, mgr, un_k, eta_ch, a_h, eta):
    """Racine u de l'équilibre longitudinal. Retourne (u, k_prec mis à jour). Voir boat._resoudre_axe."""
    un_e = 1.0 + encr
    if p > 0:
        p_arbre = eta_ch * p
        t_stat = (2 * RHO * a_h * p_arbre ** 2.0) ** (1.0 / 3.0)
        etap = eta * p
        t0 = min(etap / 1e-3, t_stat)
    else:
        t_stat = 0.0
        etap = 0.0
        t0 = 0.0
    k = k_prec
    if k < 0:
        k = 0
    elif k > N_CELL - 1:
        k = N_CELL - 1
    fa = _f_axe(-4.0 + k * W_CELL, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v, r_h, mgr,
                un_k, un_e)
    fb = _f_axe(-4.0 + (k + 1) * W_CELL, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v, r_h,
                mgr, un_k, un_e)
    for _ in range(12):
        if fa > 0 and fb <= 0:
            return 0.5 * ((-4.0 + k * W_CELL) + (-4.0 + (k + 1) * W_CELL)), k
        if not (fa > 0 or fa <= 0) or not (fb > 0 or fb <= 0):
            break
        if fa != fb:
            k2 = int(math.floor(k + fa / (fa - fb)))
        else:
            k2 = k + (1 if fa > 0 else -1)
        if k2 == k:
            k2 = k + (1 if fa > 0 else -1)
        if k2 < 0 or k2 > N_CELL - 1:
            break
        if k2 == k + 1:
            fa = fb
            fb = _f_axe(-4.0 + (k2 + 1) * W_CELL, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v,
                        r_h, mgr, un_k, un_e)
        elif k2 == k - 1:
            fb = fa
            fa = _f_axe(-4.0 + k2 * W_CELL, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v, r_h,
                        mgr, un_k, un_e)
        else:
            fa = _f_axe(-4.0 + k2 * W_CELL, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v, r_h,
                        mgr, un_k, un_e)
            fb = _f_axe(-4.0 + (k2 + 1) * W_CELL, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v,
                        r_h, mgr, un_k, un_e)
        k = k2
    # repli : bissection d'origine
    lo, hi = -4.0, 5.0
    flo = _f_axe(lo, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v, r_h, mgr, un_k, un_e)
    fhi = _f_axe(hi, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v, r_h, mgr, un_k, un_e)
    if flo * fhi > 0:
        return (lo if abs(flo) < abs(fhi) else hi), k_prec
    while hi - lo > 2e-3:
        mid = 0.5 * (lo + hi)
        fm = _f_axe(mid, p, etap, t_stat, t0, f_air_x, r_vagues, lwl, c_rf, den_fn, c_v, r_h, mgr, un_k, un_e)
        if flo * fm <= 0:
            hi = mid
            fhi = fm
        else:
            lo = mid
            flo = fm
    return 0.5 * (lo + hi), int(round((lo + 4.0) / W_CELL))


@njit(cache=True)
def equilibre(p_elec, cap, vent_u, vent_v, courant_u, courant_v, hs, vdir_u, vdir_v, encr, facteur_profil,
              k_prec, p_max, k_vagues, c_fx, c_fy, den_lat,
              lwl, c_rf, den_fn, c_v, r_h, mgr, un_k, eta_ch, a_h, eta):
    """Même calcul que boat.equilibre. Retourne (ux, uy, gu, gv, k_prec)."""
    p = min(max(p_elec, 0.0), p_max)
    if p <= 0.0:
        if vent_u != 0.0 or vent_v != 0.0:
            cap = math.atan2(vent_u, vent_v) + math.pi / 2
    sx, cx = math.sin(cap), math.cos(cap)
    yx, yy = cx, -sx
    wu, wv = facteur_profil * vent_u, facteur_profil * vent_v
    n = hypot(vdir_u, vdir_v)
    if n < 1e-6:
        fav = 0.6
    else:
        fav = 0.6 - 0.4 * ((math.sin(cap) * vdir_u + math.cos(cap) * vdir_v) / n)
    r_v = k_vagues * fav * hs * hs
    ux, uy = 0.0, 0.0
    for _ in range(3):
        gu = ux * sx + uy * yx + courant_u
        gv = ux * cx + uy * yy + courant_v
        au, av = wu - gu, wv - gv
        ax, ay = au * sx + av * cx, au * yx + av * yy
        na = hypot(ax, ay)
        fx = c_fx * na * ax
        fy = c_fy * na * ay
        ux, k_prec = resoudre_axe(p, fx, r_v, encr, k_prec, lwl, c_rf, den_fn, c_v, r_h, mgr, un_k, eta_ch, a_h, eta)
        uy = math.copysign(math.sqrt(abs(fy) / den_lat), fy)
    gu = ux * sx + uy * yx + courant_u
    gv = ux * cx + uy * yy + courant_v
    return ux, uy, gu, gv, k_prec


# ---------------------------------------------------------------------------
# Bootstrap hiérarchique (montecarlo.bootstrap), identique au bit près à la version numpy :
#   - mêmes tirages : Generator.integers de numba reproduit la suite de numpy (vérifié par test) ;
#   - même somme : ndarray.sum() = 0 + somme par paires de numpy (blocs de 8, cf. pairwise_sum).
# ---------------------------------------------------------------------------
@njit(cache=False)
def _somme_paires(a, i0, n):
    if n < 8:
        res = -0.0
        for i in range(n):
            res += a[i0 + i]
        return res
    if n <= 128:
        r0, r1, r2, r3 = a[i0], a[i0 + 1], a[i0 + 2], a[i0 + 3]
        r4, r5, r6, r7 = a[i0 + 4], a[i0 + 5], a[i0 + 6], a[i0 + 7]
        i = 8
        while i < n - (n % 8):
            r0 += a[i0 + i]
            r1 += a[i0 + i + 1]
            r2 += a[i0 + i + 2]
            r3 += a[i0 + i + 3]
            r4 += a[i0 + i + 4]
            r5 += a[i0 + i + 5]
            r6 += a[i0 + i + 6]
            r7 += a[i0 + i + 7]
            i += 8
        res = ((r0 + r1) + (r2 + r3)) + ((r4 + r5) + (r6 + r7))
        while i < n:
            res += a[i0 + i]
            i += 1
        return res
    n2 = n // 2
    n2 -= n2 % 8
    return _somme_paires(a, i0, n2) + _somme_paires(a, i0 + n2, n - n2)


# cache=False : numba ne sait pas recharger depuis son cache une fonction qui reçoit un np.random.Generator
# (violation d'accès au chargement) ; la compilation (≈ 1 s) est refaite une fois par processus.
@njit(cache=False)
def bootstrap_valeurs(rng, plat, debuts, tailles, n):
    """vals[b] de montecarlo.bootstrap. plat : valeurs des groupes mises bout à bout."""
    G = len(debuts)
    vals = np.empty(n)
    tampon = np.empty(tailles.max())
    for b in range(n):
        gs = rng.integers(0, G, G)
        tot = 0.0
        cnt = 0.0
        for g in gs:
            m = tailles[g]
            idx = rng.integers(0, m, m)
            for i in range(m):
                tampon[i] = plat[debuts[g] + idx[i]]
            tot += 0.0 + _somme_paires(tampon, 0, m)
            cnt += m
        vals[b] = tot / cnt
    return vals
