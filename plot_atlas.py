"""Station footprint atlas: each station's real 20 km disc, drawn large and all at one scale.

Grey = population density of Kontur hexagons (same classes as the corridor maps),
pale blue = water, dashed rings = 5 / 10 / 20 km, short black ticks = direction
of the line to the neighbouring stations. North is up in every disc.

Usage: python plot_atlas.py   -> out/atlas/<corridor>.png  and  out/atlas_cities.png
"""
import json, os
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.collections import PolyCollection
from shapely.geometry import Point, Polygon, LineString
from matplotlib.patches import Polygon as MplPolygon
from pyproj import Transformer
from stations import CORRIDORS, MAIN_CITY_STATIONS as CITY
from popcalc import hav_km
from plot_maps import FOOTPRINT, REGION_COL, INK, INK2, INK3, short

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
R = 20                # disc radius, km
CELL = 2.35           # inches per disc cell (disc itself is 2*R km wide)
KM = 1.75 / (2 * R)   # inches per km: every disc in every atlas uses this scale
PER_ROW = 8
LAND, WATER, EDGE = "#f4f3ef", "#dde8ee", "#c9c8c2"
BINS, GREYS = FOOTPRINT["density"]

POP = {(r["corridor"], r["station"]): r for r in json.load(open(os.path.join(OUT, "pop_kontur.json")))["rows"]}
CORR = {c["id"]: c for c in CORRIDORS}
LANDPOLY = gpd.read_file(os.path.join(HERE, "data", "ne", "ne_10m_admin_0_countries.geojson"))[["geometry"]]
LAKES = gpd.read_file(os.path.join(HERE, "data", "ne", "ne_10m_lakes.geojson"))[["geometry"]]
_HEX = {}


def hexes(cid):
    if cid not in _HEX:
        _HEX[cid] = gpd.read_parquet(os.path.join(OUT, "hex", f"{cid}.parquet"))
    return _HEX[cid]


def disc(ax, cx, cy, cid, idx):
    """Draw station idx of corridor cid as a 20 km disc centred at page coords (cx, cy) in km."""
    c = CORR[cid]
    name, lon, lat = c["stations"][idx]
    proj = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +units=km +ellps=WGS84"
    tf = Transformer.from_crs(4326, proj, always_xy=True)
    clip = Point(0, 0).buffer(R, 128)
    clip_ll = gpd.GeoSeries([clip], crs=proj).to_crs(4326).iloc[0].buffer(0.05)
    ax.add_patch(Circle((cx, cy), R, fc=WATER, ec="none", zorder=1))
    for g, fc in ((LANDPOLY, LAND), (LAKES, WATER)):
        sub = g[g.intersects(clip_ll)]
        if len(sub):
            gpd.GeoSeries(sub.geometry.clip(clip_ll), crs=4326).to_crs(proj).intersection(clip) \
                .translate(cx, cy).plot(ax=ax, facecolor=fc, edgecolor="none", zorder=1.5 if fc == LAND else 1.6)
    h = hexes(cid)
    h = h[(hav_km(lon, lat, h["lon"].values, h["lat"].values) <= R + 0.6) & (h["density"] >= BINS[0])]
    if len(h):
        v = np.stack([np.asarray(g.exterior.coords)[:6] for g in h.geometry])
        x, y = tf.transform(v[..., 0].ravel(), v[..., 1].ravel())
        v = np.column_stack([x, y]).reshape(v.shape) + (cx, cy)
        cls = np.digitize(h["density"].values, BINS) - 1
        clip_patch = Circle((cx, cy), R, transform=ax.transData)
        for k, col in enumerate(GREYS):
            sel = cls == k
            if sel.any():
                pc = PolyCollection(v[sel], facecolors=col, edgecolors=col, linewidths=0.2, zorder=2, rasterized=True)
                pc.set_clip_path(clip_patch)
                ax.add_collection(pc)
    # halfway lines to any station on the corridor within 2R: on the corridor maps, people
    # beyond the line are counted toward that station (nearest-station rule)
    disc_poly = Point(0, 0).buffer(R, 128)
    for j, (_, lo2, la2) in enumerate(c["stations"]):
        if j == idx or hav_km(lon, lat, lo2, la2) >= 2 * R:
            continue
        qx, qy = tf.transform(lo2, la2)
        n = np.hypot(qx, qy); ux, uy = qx / n, qy / n
        mx, my = qx / 2, qy / 2
        far = 4 * R  # half-plane beyond the bisector, as a big polygon, clipped to the disc
        beyond = Polygon([(mx - uy * far, my + ux * far), (mx + uy * far, my - ux * far),
                          (mx + uy * far + ux * far, my - ux * far + uy * far),
                          (mx - uy * far + ux * far, my + ux * far + uy * far)]).intersection(disc_poly)
        if beyond.is_empty:
            continue
        ax.add_patch(MplPolygon(np.asarray(beyond.exterior.coords) + (cx, cy), fc="white", alpha=0.45, ec="none", zorder=2.5))
        cut = LineString([(mx - uy * far, my + ux * far), (mx + uy * far, my - ux * far)]).intersection(disc_poly)
        if not cut.is_empty:
            ax.plot(*(np.asarray(cut.coords) + (cx, cy)).T, color=INK, lw=0.6, ls=(0, (2.2, 1.6)), alpha=0.8, zorder=4)
    # direction of the line toward neighbouring stations
    for j in (idx - 1, idx + 1):
        if 0 <= j < len(c["stations"]):
            _, lo2, la2 = c["stations"][j]
            dx, dy = tf.transform(lo2, la2)
            n = np.hypot(dx, dy)
            ux, uy = dx / n, dy / n
            ax.plot([cx, cx + ux * R], [cy, cy + uy * R], color=INK, lw=1.0, zorder=3, solid_capstyle="butt",
                    ls="-" if c["status"] == "existing" else (0, (4, 2)) if c["status"] == "building" else (0, (1.5, 1.5)))
            ax.text(cx + ux * (R + 2.2), cy + uy * (R + 2.2), "→ " + short(c["stations"][j][0]) if ux >= 0 else short(c["stations"][j][0]) + " ←",
                    fontsize=4.6, color=INK3, ha="left" if ux >= 0 else "right", va="center", zorder=3,
                    rotation=0)
    for r, lw in ((5, 0.6), (10, 0.6), (20, 0.8)):
        ax.add_patch(Circle((cx, cy), r, fc="none", ec=INK, lw=lw, ls=(0, (2.2, 1.6)), alpha=0.8, zorder=4))
    ax.add_patch(Circle((cx, cy), 0.9, fc=INK, ec="white", lw=0.5, zorder=5))
    p = POP[(cid, name)]
    col = REGION_COL[c["region"]]
    ax.text(cx - R, cy - R - 3.5, short(name), fontsize=7.2, weight="bold", color=INK, va="top", ha="left")
    ax.text(cx - R, cy - R - 9.2, "  ".join(f"{r} km {fmt(p[f'raw_{r}'])}" for r in (5, 10, 20)),
            fontsize=5.6, color=INK2, va="top", ha="left")
    # small bar: share of the 20 km population that lives within 5 km
    s5 = p["raw_5"] / p["raw_20"] if p["raw_20"] else 0
    ax.add_patch(plt.Rectangle((cx - R, cy - R - 15.5), 2 * R, 1.6, fc="#e4e3de", ec="none"))
    ax.add_patch(plt.Rectangle((cx - R, cy - R - 15.5), 2 * R * s5, 1.6, fc=col, ec="none"))
    ax.text(cx + R, cy - R - 17.8, f"{s5:.0%} of the 20 km population within 5 km", fontsize=4.8, color=INK3, va="top", ha="right")


def fmt(v):
    return f"{v/1e6:.1f} M" if v >= 1e6 else f"{v/1e3:.0f}k"


def page(items, title, subtitle, path, per_row=PER_ROW):
    n = len(items)
    rows = (n + per_row - 1) // per_row
    cols = min(n, per_row)
    cw = CELL / KM               # cell width in km of page space
    ch = cw * 1.22
    head = 52
    W, H = cols * cw + 20, rows * ch + head + 30
    fig = plt.figure(figsize=(W * KM, H * KM))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(-H, 0); ax.set_aspect("equal"); ax.axis("off")
    ax.text(8, -6, title, fontsize=12, weight="bold", color=INK, va="top")
    ax.text(8, -22, subtitle, fontsize=6.6, color=INK2, va="top", linespacing=1.5)
    # legend
    lx = 8
    for lab, col in zip([f"{b:,}–{BINS[i+1]:,}" if i + 1 < len(BINS) else f"{b:,}+" for i, b in enumerate(BINS)], GREYS):
        ax.add_patch(plt.Rectangle((lx, -41), 5, 5, fc=col, ec="none"))
        ax.text(lx + 7, -38.5, lab, fontsize=5.6, color=INK2, va="center"); lx += 40
    ax.text(lx, -38.5, "people per km²", fontsize=5.6, color=INK2, va="center"); lx += 48
    ax.add_patch(plt.Rectangle((lx, -41), 5, 5, fc=WATER, ec="none")); ax.text(lx + 7, -38.5, "water", fontsize=5.6, color=INK2, va="center")
    for i, (cid, idx) in enumerate(items):
        r_, c_ = divmod(i, per_row)
        disc(ax, 10 + c_ * cw + cw / 2, -head - r_ * ch - R - 4, cid, idx)
    fig.savefig(path, dpi=220, facecolor="white")
    plt.close(fig)
    print("wrote", path)


SUB = ("Each disc is the real 20 km radius around a station, north up, all at the same scale. Dashed rings: 5, 10 and 20 km. "
       "Black ticks: direction of the line.\n"
       "A straight dashed line with a pale wash marks the halfway point to a nearby station: on the corridor maps, people beyond it count toward that station. "
       "Numbers: residents within each radius (Kontur Population 2023). "
       "The bar shows how much of the 20 km population lives within 5 km.")

if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "atlas"), exist_ok=True)
    for c in CORRIDORS:
        page([(c["id"], i) for i in range(len(c["stations"]))], f"{c['name']}: station footprints", SUB,
             os.path.join(OUT, "atlas", f"{c['id']}.png"))
    # big-city comparison, sorted by population within 10 km
    big = [(c["id"], i) for c in CORRIDORS for i, s in enumerate(c["stations"])
           if s[0] in CITY and POP[(c["id"], s[0])]["raw_50"] >= 2.5e6]
    big.sort(key=lambda t: -POP[(t[0], CORR[t[0]]["stations"][t[1]][0])]["raw_10"])
    page(big, "Main-city stations compared: what's inside 20 km", SUB + " Sorted by residents within 10 km.",
         os.path.join(OUT, "atlas_cities.png"), per_row=9)
