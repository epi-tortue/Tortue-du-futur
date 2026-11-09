"""Figures, carte interactive et journal de bord (complété au fil des étapes)."""
from __future__ import annotations

from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import environment as E  # noqa: E402
from .config import DATA, OUT  # noqa: E402
from .geo import NM, densifier_ligne, haversine  # noqa: E402


MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def _dessiner_cote(ax, terre, cadre):
    from shapely.geometry import box
    g = terre.intersection(box(*cadre))
    polys = getattr(g, "geoms", [g])
    for p in polys:
        if p.is_empty or p.geom_type != "Polygon":
            continue
        x, y = p.exterior.xy
        ax.fill(x, y, color="#d9d4c7", ec="#8a8576", lw=0.4, zorder=3)


def _decor(ax, cfg, terre, cadre):
    _dessiner_cote(ax, terre, cadre)
    for nom, coul in (("ouest", "#2b6cb0"), ("est", "#c05621")):
        l = densifier_ligne(cfg["lignes"][nom])
        ax.plot(l[:, 1], l[:, 0], color=coul, lw=1.6, ls="--", zorder=4)
    d, a = cfg["mission"]["depart"], cfg["mission"]["arrivee"]
    # orthodromie départ -> arrivée
    from .geo import R_TERRE  # noqa: F401
    t = np.linspace(0, 1, 100)
    la1, lo1, la2, lo2 = map(np.radians, (d["lat"], d["lon"], a["lat"], a["lon"]))
    dd = haversine(d["lat"], d["lon"], a["lat"], a["lon"]) / 6_371_000.0
    A = np.sin((1 - t) * dd) / np.sin(dd)
    B = np.sin(t * dd) / np.sin(dd)
    x = A * np.cos(la1) * np.cos(lo1) + B * np.cos(la2) * np.cos(lo2)
    y = A * np.cos(la1) * np.sin(lo1) + B * np.cos(la2) * np.sin(lo2)
    z = A * np.sin(la1) + B * np.sin(la2)
    ax.plot(np.degrees(np.arctan2(y, x)), np.degrees(np.arctan2(z, np.hypot(x, y))),
            color="k", lw=1.0, zorder=5)
    ax.plot(d["lon"], d["lat"], "o", ms=7, mfc="#2f855a", mec="k", zorder=6)
    r_deg = a["rayon_km"] / 111.0
    th = np.linspace(0, 2 * np.pi, 80)
    ax.plot(a["lon"] + r_deg * np.cos(th) / np.cos(np.radians(a["lat"])),
            a["lat"] + r_deg * np.sin(th), color="#c05621", lw=1.5, zorder=6)
    ax.set_xlim(cadre[0], cadre[2])
    ax.set_ylim(cadre[1], cadre[3])
    ax.set_aspect(1 / np.cos(np.radians(49)))
    ax.set_xlabel("longitude (°)")
    ax.set_ylabel("latitude (°)")


def figure_controle(cfg: dict, date: str = "2026-01-01T12:00") -> str:
    quand = datetime.fromisoformat(date).replace(tzinfo=None)
    g = cfg["donnees"]["grille"]
    terre, _ = E.charger_cote()
    lats, lons, met = E.instantane(cfg, g, quand, "meteo", ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"])
    _, _, mar = E.instantane(cfg, g, quand, "marine",
                             ["wave_height", "wave_direction", "ocean_current_velocity", "ocean_current_direction",
                              "sea_surface_temperature"])
    LO, LA = np.meshgrid(lons, lats)
    cadre = (lons[0] - 1, lats[0] - 1, lons[-1] + 1, lats[-1] + 1)

    fig = plt.figure(figsize=(16, 11), constrained_layout=True)
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.75])

    # (a) vent
    ax = fig.add_subplot(gs[0, 0])
    pc = ax.pcolormesh(LO, LA, met["wind_speed_10m"], cmap="viridis", shading="nearest", vmin=0, vmax=25, zorder=1)
    u, v = E._uv_depuis(np.ones_like(met["wind_speed_10m"]), met["wind_direction_10m"], True)
    ax.quiver(LO, LA, u, v, color="w", scale=40, width=0.003, zorder=2)
    fig.colorbar(pc, ax=ax, label="vent 10 m (m/s) — ERA5")
    _decor(ax, cfg, terre, cadre)
    ax.set_title(f"(a) Vent 10 m, {quand:%d/%m/%Y %H:%M} UTC (flèches : direction vers laquelle il souffle)")

    # (b) vagues
    ax = fig.add_subplot(gs[0, 1])
    pc = ax.pcolormesh(LO, LA, mar["wave_height"], cmap="magma_r", shading="nearest", vmin=0, vmax=10, zorder=1)
    u, v = E._uv_depuis(np.ones_like(mar["wave_height"]), mar["wave_direction"], True)
    ax.quiver(LO, LA, u, v, color="k", scale=40, width=0.003, zorder=2)
    fig.colorbar(pc, ax=ax, label="Hs (m) — Open-Meteo Marine")
    _decor(ax, cfg, terre, cadre)
    ax.set_title("(b) Hauteur significative des vagues (flèches : propagation)")

    # (c) courants + SST
    ax = fig.add_subplot(gs[1, 0])
    pc = ax.pcolormesh(LO, LA, mar["sea_surface_temperature"], cmap="coolwarm", shading="nearest", vmin=0, vmax=18, zorder=1)
    cu, cv = E._uv_depuis(mar["ocean_current_velocity"], mar["ocean_current_direction"], False)
    q = ax.quiver(LO, LA, cu, cv, color="k", scale=8, scale_units="width", width=0.003, zorder=2)
    ax.quiverkey(q, 0.88, 1.02, 0.5, "0,5 m/s", labelpos="E", coordinates="axes")
    fig.colorbar(pc, ax=ax, label="température de surface (°C)")
    _decor(ax, cfg, terre, cadre)
    ax.set_title("(c) Courant de surface (flèches) et SST")

    # (d) pêche janvier
    ax = fig.add_subplot(gs[1, 1])
    fg = DATA / "gfw.npz"
    if fg.exists():
        z = np.load(fg)
        m = list(z["mois"]).index(quand.strftime("%Y-%m")) if quand.strftime("%Y-%m") in list(z["mois"]) else 0
        P = z["peche_h_km2"][m]
        Cm = z["commerce_h_km2"][m]
        GLO, GLA = np.meshgrid(z["lons"], z["lats"])
        pc = ax.pcolormesh(GLO, GLA, np.ma.masked_less_equal(P, 0), cmap="YlOrRd",
                           norm=matplotlib.colors.LogNorm(1e-4, 1e-1), shading="nearest", zorder=1)
        fig.colorbar(pc, ax=ax, label="effort de pêche apparent (h/km²/mois) — GFW")
        cs = ax.contour(GLO, GLA, Cm, levels=[np.nanpercentile(Cm[Cm > 0], 90)] if (Cm > 0).any() else [],
                        colors="#2b6cb0", linewidths=0.8, zorder=2)
        ax.set_title(f"(d) Pêche {z['mois'][m]} ; contour bleu : 10 % des cellules les plus fréquentées par cargos/pétroliers")
    else:
        ax.text(0.5, 0.5, "GFW pas encore en cache", ha="center", transform=ax.transAxes)
        ax.set_title("(d) Pêche (GFW)")
    _decor(ax, cfg, terre, cadre)

    # (e) séries temporelles au point de départ, janvier
    ax = fig.add_subplot(gs[2, :])
    d = cfg["mission"]["depart"]
    (la, lo), t, s = E.serie_point(cfg, g, d["lat"], d["lon"], quand.strftime("%Y-%m"), "meteo",
                                   ["wind_speed_10m", "wind_gusts_10m", "temperature_2m"])
    _, t2, s2 = E.serie_point(cfg, g, d["lat"], d["lon"], quand.strftime("%Y-%m"), "marine",
                              ["wave_height", "sea_surface_temperature"])
    tt = [datetime.fromtimestamp(x, timezone.utc) for x in t]
    ax.plot(tt, s["wind_speed_10m"], label="vent 10 m (m/s)", color="#2f855a")
    ax.plot(tt, s["wind_gusts_10m"], label="rafales (m/s)", color="#2f855a", alpha=0.35)
    ax.plot(tt, s2["wave_height"], label="Hs (m)", color="#6b46c1")
    ax.plot(tt, s["temperature_2m"], label="T air (°C)", color="#c53030")
    ax.plot(tt, s2["sea_surface_temperature"], label="SST (°C)", color="#c53030", ls="--")
    ax.axhline(0, color="k", lw=0.5)
    ax.axhline(5, color="#c53030", lw=0.5, ls=":")
    ax.text(tt[2], 5.3, "5 °C : seuil de charge pleine LiFePO4", fontsize=8, color="#c53030")
    ax.axvline(quand.replace(tzinfo=timezone.utc), color="k", ls=":")
    ax.legend(ncol=5, fontsize=9, loc="upper right")
    ax.set_title(f"(e) Nœud de grille le plus proche du départ ({la:.0f}°N {abs(lo):.0f}°W), {MOIS[quand.month-1]} {quand.year}")
    ax.grid(alpha=0.3)

    dist = haversine(d["lat"], d["lon"], cfg["mission"]["arrivee"]["lat"], cfg["mission"]["arrivee"]["lon"]) / NM
    fig.suptitle(f"Contrôle des données réelles — départ {d['lat']}°N {abs(d['lon'])}°W → cercle d'arrivée "
                 f"{cfg['mission']['arrivee']['lat']}°N {abs(cfg['mission']['arrivee']['lon'])}°W "
                 f"(orthodromie {dist:.0f} nm). Grille {g['pas']:g}°. Tirets : lignes Microtransat Ouest/Est.",
                 fontsize=12)
    OUT.mkdir(exist_ok=True)
    f = OUT / f"controle_{quand:%Y%m%d_%H%M}.png"
    fig.savefig(f, dpi=110)
    plt.close(fig)
    return str(f)


# ---------------------------------------------------------------------------
# Trajectoires et séries temporelles
# ---------------------------------------------------------------------------
COULEURS = ["#2b6cb0", "#c05621", "#2f855a", "#6b46c1", "#b7791f", "#c53030", "#319795", "#4a5568"]


def _dates(t):
    return [datetime.fromtimestamp(x, timezone.utc) for x in t]


def carte_trajectoires(cfg: dict, resultats: dict, nom: str, titre: str, fond_peche: bool = True) -> str:
    """resultats : {étiquette: Resultat}. Carte statique (matplotlib)."""
    terre, _ = E.charger_cote()
    cadre = (-58, 41, -6, 57)
    fig, ax = plt.subplots(figsize=(13, 7), constrained_layout=True)
    if fond_peche and (DATA / "gfw.npz").exists():
        z = np.load(DATA / "gfw.npz")
        P = z["peche_h_km2"].mean(axis=0)
        GLO, GLA = np.meshgrid(z["lons"], z["lats"])
        pc = ax.pcolormesh(GLO, GLA, np.ma.masked_less_equal(P, 0), cmap="Greys", alpha=0.45,
                           norm=matplotlib.colors.LogNorm(1e-4, 1e-1), shading="nearest", zorder=1)
        fig.colorbar(pc, ax=ax, shrink=0.7, label="effort de pêche moyen 2026 (h/km²/mois, GFW)")
    for k, (etq, r) in enumerate(resultats.items()):
        tr = r.traj
        c = COULEURS[k % len(COULEURS)]
        ax.plot(tr["lon"], tr["lat"], color=c, lw=1.6, zorder=7, label=f"{etq} — {r.fin} en {r.jours:.0f} j")
        # marques journalières tous les 5 jours
        j = ((tr["t"] - tr["t"][0]) / 86400.0)
        for d in range(5, int(j[-1]) + 1, 5):
            i = int(np.searchsorted(j, d))
            if i < len(j):
                ax.plot(tr["lon"][i], tr["lat"][i], "o", ms=3, color=c, zorder=8)
        if "estime_lat" in tr:
            ax.plot(tr["estime_lon"], tr["estime_lat"], color=c, lw=0.8, ls=":", zorder=7)
        ax.plot(tr["lon"][-1], tr["lat"][-1], "X", ms=9, color=c, mec="k", zorder=9)
    _decor(ax, cfg, terre, cadre)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title(titre + " (points : tous les 5 jours ; croix : fin)")
    f = OUT / f"{nom}.png"
    fig.savefig(f, dpi=110)
    plt.close(fig)
    return str(f)


def courbes_run(cfg: dict, r, nom: str, titre: str) -> str:
    tr = r.traj
    d = _dates(tr["t"])
    panneaux = [("vitesse (m/s)", [("v_surf", "surface (eau)"), ("v_fond", "fond")]),
                ("distance restante (nm)", [("dist_restante_nm", None)]),
                ("vent 10 m (m/s) / Hs (m)", [("vent", "vent"), ("rafales", "rafales"), ("hs", "Hs")]),
                ("courant (m/s)", [("courant", None)]),
                ("température (°C)", [("sst", "SST"), ("t_air", "air"), ("t_bat", "batterie")]),
                ("puissance (W)", [("p_moteur", "moteur"), ("p_solaire", "solaire"), ("p_chauffage", "chauffage")]),
                ("SOC batterie (%)", [("soc_pct", None)]),
                ("largeur boîte Codac (km)", [("boite_km", None)])]
    tr = dict(tr)
    if "vent" not in tr:
        tr["vent"] = np.hypot(tr["vent_u"], tr["vent_v"])
    if "courant" not in tr:
        tr["courant"] = np.hypot(tr["courant_u"], tr["courant_v"])
    panneaux = [(t_, [(k, l) for k, l in s_ if k in tr]) for t_, s_ in panneaux]
    panneaux = [p for p in panneaux if p[1]]
    fig, axs = plt.subplots(len(panneaux), 1, figsize=(13, 2.1 * len(panneaux)), sharex=True,
                            constrained_layout=True)
    for ax, (ttl, series) in zip(axs, panneaux):
        for k, (cle, lab) in enumerate(series):
            ax.plot(d, tr[cle], lw=0.9, label=lab, color=COULEURS[k])
        ax.set_ylabel(ttl, fontsize=8)
        ax.grid(alpha=0.3)
        if any(l for _, l in series):
            ax.legend(fontsize=7, ncol=3, loc="upper right")
    for ev in r.evenements:
        if ev.type not in ("depart",):
            for ax in axs:
                ax.axvline(datetime.fromtimestamp(ev.t, timezone.utc), color="#c53030", lw=0.6, alpha=0.6)
    axs[0].set_title(titre)
    f = OUT / f"{nom}.png"
    fig.savefig(f, dpi=100)
    plt.close(fig)
    return str(f)
