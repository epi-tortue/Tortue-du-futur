"""Tâches longues en arrière-plan pour l'interface graphique.

Une tâche = `python main.py <commande> ...` lancé dans un sous-processus, sortie dans out/taches/<id>.log.
Pourquoi un sous-processus plutôt qu'un thread : le Monte-Carlo crée lui-même un pool de processus, un
calcul de plusieurs minutes ne doit pas bloquer l'interface, et l'annulation doit pouvoir tout arrêter
(sous-processus ET processus du pool). L'état est écrit sur disque : il survit au rechargement de la page.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import OUT, RACINE

DOSSIER = OUT / "taches"
_RE_RUNS = re.compile(r"(\d+)/(\d+) runs")
_RE_ETAPE = re.compile(r"^\[(\d+)(?:-\d+)?/(\d+)\]")


def _meta(tid: str) -> Path:
    return DOSSIER / f"{tid}.json"


def lancer(args: list[str], titre: str) -> str:
    """Démarre `python main.py *args` ; retourne l'identifiant de la tâche."""
    DOSSIER.mkdir(parents=True, exist_ok=True)
    tid = time.strftime("%Y%m%d_%H%M%S") + f"_{os.getpid() % 1000:03d}{int(time.time() * 1000) % 1000:03d}"
    log = DOSSIER / f"{tid}.log"
    cmd = [sys.executable, "-u", str(RACINE / "main.py"), *args]
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kw["start_new_session"] = True
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    with open(log, "w", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, cwd=str(RACINE), stdout=f, stderr=subprocess.STDOUT, env=env, **kw)
    _meta(tid).write_text(json.dumps({"id": tid, "titre": titre, "args": args, "pid": p.pid,
                                      "debut": time.time(), "statut": "en_cours"}), encoding="utf-8")
    return tid


def _vivant(pid: int) -> bool:
    if sys.platform == "win32":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def etat(tid: str) -> dict:
    m = json.loads(_meta(tid).read_text(encoding="utf-8"))
    log = DOSSIER / f"{tid}.log"
    texte = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    if m["statut"] == "en_cours" and not _vivant(m["pid"]):
        m["statut"] = "termine" if "Traceback" not in texte else "erreur"
        m["fin"] = time.time()
        _meta(tid).write_text(json.dumps(m), encoding="utf-8")
    m["log"] = texte
    m["progression"] = progression(texte, m["statut"])
    return m


def progression(texte: str, statut: str = "en_cours") -> float:
    """Fraction [0 ; 1] estimée d'après le journal : « i/N runs », pondéré par l'étape « [k/7] » du rapport."""
    if statut != "en_cours":
        return 1.0
    frac, etape, n_etapes = 0.0, None, None
    for ligne in texte.splitlines():
        m = _RE_ETAPE.match(ligne.strip())
        if m:
            etape, n_etapes = int(m.group(1)), int(m.group(2))
            frac = 0.0
        m = _RE_RUNS.search(ligne)
        if m and int(m.group(2)) > 0:
            frac = int(m.group(1)) / int(m.group(2))
    if etape is None:
        return min(frac, 0.99)
    if etape <= 3:          # rapport : les Monte-Carlo (étapes 1 à 3) font l'essentiel du temps
        return min(0.85 * frac, 0.85)
    return min(0.85 + 0.15 * (etape - 3) / max(1, n_etapes - 3), 0.99)


def annuler(tid: str) -> None:
    """Arrête la tâche et tous ses sous-processus (le pool du Monte-Carlo compris)."""
    m = json.loads(_meta(tid).read_text(encoding="utf-8"))
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(m["pid"]), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(m["pid"]), signal.SIGTERM)
        except OSError:
            pass
    m["statut"] = "annule"
    m["fin"] = time.time()
    _meta(tid).write_text(json.dumps(m), encoding="utf-8")


def lister() -> list[dict]:
    if not DOSSIER.exists():
        return []
    out = []
    for f in sorted(DOSSIER.glob("*.json"), reverse=True):
        try:
            out.append(etat(f.stem))
        except (OSError, ValueError):
            continue
    return out


def fichiers_produits(texte: str) -> list[str]:
    """Chemins de fichiers de out/ cités dans le journal (cartes, courbes, journaux, figures)."""
    vus = []
    for ligne in texte.splitlines():
        for mot in re.findall(r"[A-Za-z]:[\\/][^\s]+|/[^\s]+", ligne):
            mot = mot.strip(" ,;:()")
            if Path(mot).suffix in (".html", ".png", ".md", ".json") and Path(mot).exists() and mot not in vus:
                vus.append(mot)
    return vus
