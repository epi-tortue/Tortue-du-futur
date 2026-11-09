"""Chargement de config.yaml (+ secrets.yaml) avec surcharges en ligne de commande."""
from __future__ import annotations

import copy
import os
import warnings
from pathlib import Path

import yaml

# Le numpy installé dans le site utilisateur émet des avertissements bénins
# (sondage des types flottants) à l'import ; on les masque.
warnings.filterwarnings("ignore", message=".*does not match any known type.*")
warnings.filterwarnings("ignore", message="overflow encountered in divide")

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
OUT = RACINE / "out"


def charger(chemin: str | Path | None = None, **surcharges) -> dict:
    chemin = Path(chemin) if chemin else RACINE / "config.yaml"
    with open(chemin, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg = copy.deepcopy(cfg)
    for cle, val in surcharges.items():
        if val is None:
            continue
        d = cfg
        parties = cle.split(".")
        for p in parties[:-1]:
            d = d.setdefault(p, {})
        d[parties[-1]] = val
    return cfg


def jeton_gfw(cfg: dict) -> str | None:
    tok = os.environ.get("GFW_API_ACCESS_TOKEN")
    if tok:
        return tok
    f = RACINE / cfg["donnees"]["gfw"].get("token_fichier", "secrets.yaml")
    if f.exists():
        with open(f, encoding="utf-8") as fh:
            return (yaml.safe_load(fh) or {}).get("gfw_api_access_token")
    return None
