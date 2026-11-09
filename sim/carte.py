"""Carte interactive HTML (folium) d'une mission."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .config import DATA, OUT
from .geo import haversine

ICONES = {3: ("red", "remove-sign"), 2: ("orange", "warning-sign"), 1: ("blue", "info-sign")}


def date_fr(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%d/%m/%Y %H:%M")


def carte_folium(cfg: dict, r, nom: str, titre: str = "", autres: dict | None = None) -> str:
    """r : Resultat détaillé. autres : {étiquette: [(lat, lon), ...]} traces supplémentaires."""
    import folium
    from folium.plugins import HeatMap

    tr = r.traj
    m = folium.Map(location=[50, -32], zoom_start=4, tiles="CartoDB positron")
    if (DATA / "gfw.npz").exists():
        z = np.load(DATA / "gfw.npz")
        mois = {datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m") for t in tr["t"][::20]}
        idx = [i for i, mm in enumerate(z["mois"]) if str(mm) in mois] or list(range(len(z["mois"])))
        P = z["peche_h_km2"][idx].mean(axis=0)
        pts = [[float(la), float(lo), float(P[i, j])] for i, la in enumerate(z["lats"])
               for j, lo in enumerate(z["lons"]) if P[i, j] > 1e-4]
        if pts:
            vmax = float(np.percentile([p[2] for p in pts], 98))
            HeatMap([[a, b, min(c / vmax, 1.0)] for a, b, c in pts], name="Effort de pêche GFW (mois de la mission)",
                    radius=14, blur=18, min_opacity=0.25).add_to(m)
        Cm = z["commerce_h_km2"][idx].mean(axis=0)
        if (Cm > 0).any():
            seuil = np.percentile(Cm[Cm > 0], 95)
            g = folium.FeatureGroup(name="Zones de danger : trafic commercial dense (5 % des cellules)", show=False)
            demi = float(z["lats"][1] - z["lats"][0]) / 2
            for i, la in enumerate(z["lats"]):
                for j, lo in enumerate(z["lons"]):
                    if Cm[i, j] >= seuil:
                        folium.Rectangle([[la - demi, lo - demi], [la + demi, lo + demi]], color=None, fill=True,
                                         fill_color="#2b6cb0", fill_opacity=0.25).add_to(g)
            g.add_to(m)
    for nomL, coul in (("ouest", "#2b6cb0"), ("est", "#c05621")):
        folium.PolyLine(cfg["lignes"][nomL], color=coul, weight=2, dash_array="6",
                        tooltip=f"Ligne Microtransat {nomL}").add_to(m)
    d, a = cfg["mission"]["depart"], cfg["mission"]["arrivee"]
    folium.Marker([d["lat"], d["lon"]], tooltip="Largage", icon=folium.Icon(color="green", icon="flag")).add_to(m)
    folium.Circle([a["lat"], a["lon"]], radius=a["rayon_km"] * 1000, color="#c05621", fill=False,
                  tooltip="Cercle d'arrivée (25 km)").add_to(m)
    pas = max(1, len(tr["t"]) // 3000)
    folium.PolyLine(list(zip(tr["lat"][::pas], tr["lon"][::pas])), color="#1a202c", weight=2.5,
                    tooltip="Trajectoire vraie").add_to(m)
    if "estime_lat" in tr:
        folium.PolyLine(list(zip(tr["estime_lat"][::pas], tr["estime_lon"][::pas])), color="#3182ce", weight=1.5,
                        dash_array="4", tooltip="Position estimée (centre de la boîte Codac)").add_to(m)
    gb = folium.FeatureGroup(name="Boîtes Codac pendant les pertes GPS")
    for (t, la0, la1, lo0, lo1) in r.stats.get("boites", []):
        folium.Rectangle([[la0, lo0], [la1, lo1]], color="#805ad5", weight=1, fill=True, fill_opacity=0.04,
                         tooltip=f"{date_fr(t)} : boîte de {haversine(la0, lo0, la1, lo0) / 1000:.1f} km").add_to(gb)
    gb.add_to(m)
    t0 = tr["t"][0]
    gj = folium.FeatureGroup(name="Positions quotidiennes", show=False)
    for k in range(0, int((tr["t"][-1] - t0) / 86400) + 1):
        i = min(int(np.searchsorted(tr["t"], t0 + k * 86400)), len(tr["t"]) - 1)
        folium.CircleMarker([float(tr["lat"][i]), float(tr["lon"][i])], radius=2, color="#1a202c",
                            tooltip=f"Jour {k} — {date_fr(tr['t'][i])}").add_to(gj)
    gj.add_to(m)
    ge = folium.FeatureGroup(name="Événements")
    for e in r.evenements:
        if e.gravite < 1:
            continue
        coul, ic = ICONES.get(min(e.gravite, 3), ("gray", "info-sign"))
        j = (e.t - t0) / 86400
        folium.Marker([e.lat, e.lon], icon=folium.Icon(color=coul, icon=ic),
                      tooltip=f"J{j:.1f} {e.probleme or ''} {e.type}",
                      popup=folium.Popup(f"<b>Jour {j:.1f}</b> ({date_fr(e.t)})<br>{e.probleme or ''} {e.texte}",
                                         max_width=320)).add_to(ge)
    ge.add_to(m)
    for k, (etq, trace) in enumerate((autres or {}).items()):
        folium.PolyLine(trace, color=["#38a169", "#d69e2e", "#e53e3e"][k % 3], weight=2, opacity=0.8,
                        tooltip=etq).add_to(m)
    folium.LayerControl().add_to(m)
    if titre:
        m.get_root().html.add_child(folium.Element(
            f'<div style="position:fixed;top:8px;left:50px;z-index:9999;background:white;padding:6px 10px;'
            f'border-radius:4px;font:14px sans-serif;box-shadow:0 1px 4px #999">{titre}</div>'))
    OUT.mkdir(exist_ok=True)
    f = OUT / f"{nom}.html"
    m.save(str(f))
    return str(f)
