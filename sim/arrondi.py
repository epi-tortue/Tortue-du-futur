"""Mode d'arrondi du processeur : au plus proche partout, vers le haut seulement pendant les calculs Codac.

Pourquoi ce module [H78]
------------------------
La bibliothèque d'intervalles de Codac (GAOL) met le processeur en arrondi VERS LE HAUT dès
`import codac`, et ne le rétablit jamais : c'est ainsi qu'elle garantit ses bornes à moindre coût
(borne basse = −((−a) − b) calculée vers le haut). Mais ce mode s'applique alors à TOUT le
processus : l'arithmétique Python et numpy du simulateur était faite en arrondi vers le haut, et
seulement à partir du moment où Codac avait été importé. Conséquences :
  - un même run ne donnait pas les mêmes bits selon qu'il était le premier d'un processus du
    Monte-Carlo (début calculé au plus proche) ou non : résultats dépendants de l'ordonnancement ;
  - le noyau compilé (numba) et la version Python ne coïncidaient plus.
Effet physique négligeable (1 ulp par opération), mais la reproductibilité au bit près est la base
du test de non-régression et des comparaisons sur mêmes graines.

Utilisation : `with vers_le_haut(): <appels Codac qui calculent>`. Le reste du code tourne au plus proche.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import platform
import sys
from contextlib import contextmanager

_regler = None          # fonction(mode) ; None = plateforme non gérée (on ne touche à rien)
PROCHE = HAUT = None

try:
    if sys.platform == "win32":
        _ctl = ctypes.cdll.ucrtbase._controlfp
        _ctl.restype = ctypes.c_uint
        _ctl.argtypes = [ctypes.c_uint, ctypes.c_uint]
        _MCW_RC = 0x300
        PROCHE, HAUT = 0x000, 0x200            # _RC_NEAR, _RC_UP

        def _regler(mode):
            _ctl(mode, _MCW_RC)

        def mode_actuel():
            return _ctl(0, 0) & _MCW_RC
    else:
        _libm = ctypes.CDLL(ctypes.util.find_library("m") or "libm.so.6")
        _libm.fesetround.argtypes = [ctypes.c_int]
        _libm.fegetround.restype = ctypes.c_int
        if platform.machine().lower() in ("arm64", "aarch64"):
            PROCHE, HAUT = 0x000000, 0x400000
        else:                                   # x86-64 (glibc, macOS)
            PROCHE, HAUT = 0x000, 0x800

        def _regler(mode):
            _libm.fesetround(mode)

        def mode_actuel():
            return _libm.fegetround()
except (OSError, AttributeError):              # pragma: no cover - plateforme exotique
    _regler = None

    def mode_actuel():
        return None


def au_plus_proche():
    if _regler is not None:
        _regler(PROCHE)


def haut():
    if _regler is not None:
        _regler(HAUT)


@contextmanager
def vers_le_haut():
    """Arrondi vers le haut le temps d'un calcul Codac, puis retour au plus proche."""
    haut()
    try:
        yield
    finally:
        au_plus_proche()
