"""Data + ground images for the oblique "prism" view on the page.

Each corridor is rotated so its principal axis runs left→right. For each radius,
each station's catchment is its r-km circle cut by its Voronoi cell (the same
nearest-station rule as the counts). The page extrudes these into prisms.

Outputs:
  out/prisms.json          corridor geometry in rotated km (x right, y "north" = away from viewer)
  out/ground/<cid>.png     land / water / density shading in the same coordinates

Usage: python build_prisms.py
"""
import json, os
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from shapely.geometry import Point, MultiPoint, box
from shapely.ops import voronoi_diagram
from pyproj import Transformer
from stations import CORRIDORS
from popcalc import hav_km
from plot_maps import FOOTPRINT, short

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RADII = [5, 10, 20]
PAD = 55          # km of ground shown around the stations
PX_PER_KM = 3     # ground image resolution
LAND, WATER, BORDER = "#efeee9", "#dfe8ed", "#d2d1cb"
BINS, GREYS = FOOTPRINT["density"]

POP = {(r["corridor"], r["station"]): r for r in json.load(open(os.path.join(OUT, "pop_kontur.json")))["rows"]}
NE = os.path.join(HERE, "data", "ne")
ADM0 = gpd.read_file(os.path.join(NE, "ne_10m_admin_0_countries.geojson"))[["geometry"]]
ADM1 = gpd.read_file(os.path.join(NE, "ne_10m_admin_1_states_provinces_lakes.geojson"))[["geometry"]]


def rnd(a, d=2):
    return [[round(float(x), d), round(float(y), d)] for x, y in a]


def corridor(c):
    sts = c["stations"]
    lon0, lat0 = np.mean([s[1] for s in sts]), np.mean([s[2] for s in sts])
    proj = f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +units=km +ellps=WGS84"
    tf = Transformer.from_crs(4326, proj, always_xy=True)
    xy = np.array([tf.transform(s[1], s[2]) for s in sts])
    # rotate so the principal axis points along +x (smallest rotation that does it)
    v = np.linalg.svd(xy - xy.mean(0))[2][0]
    if v[0] < 0:
        v = -v
    phi = -np.degrees(np.arctan2(v[1], v[0]))
    t = np.radians(phi)
    R = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
    xy = xy @ R.T
    # North must never point downward. The smallest rotation already guarantees
    # that; the check stays as a guard for a route turned exactly 90°.
    if (R @ np.array([0.0, 1.0]))[1] < 0:
        R = -R
        xy = -xy
    x0, y0 = xy.min(0) - PAD
    x1, y1 = xy.max(0) + PAD

    # catchments: circle ∩ Voronoi cell, per radius
    env = box(x0 - 500, y0 - 500, x1 + 500, y1 + 500)
    if len(xy) > 1:
        cells = list(voronoi_diagram(MultiPoint([tuple(p) for p in xy]), envelope=env).geoms)
        cell_of = [next(g for g in cells if g.contains(Point(p))) for p in xy]
    else:
        cell_of = [env]
    stations = []
    for i, (s, p) in enumerate(zip(sts, xy)):
        pr = POP[(c["id"], s[0])]
        cat = {}
        for r in RADII:
            g = Point(p).buffer(r, 48).intersection(cell_of[i])
            g = g.simplify(0.05)
            ring = np.asarray(g.exterior.coords)[:-1]
            # counter-clockwise, so outward normals are well defined on the page
            if g.exterior.is_ccw is False:
                ring = ring[::-1]
            cat[str(r)] = dict(poly=rnd(ring), pop=round(pr[f"dedup_{r}"]), area=round(g.area, 1))
        stations.append(dict(name=short(s[0]), full=s[0], x=round(float(p[0]), 2), y=round(float(p[1]), 2), c=cat))

    ground(c["id"], proj, R, (x0, y0, x1, y1), sts)
    north = (R @ np.array([0.0, 1.0])).tolist()
    print(f"   {c['id']:9s} turn {phi:6.1f}°  north → ({north[0]:+.2f}, {north[1]:+.2f})  {short(sts[0][0]) if xy[0,0] < xy[-1,0] else short(sts[-1][0])} on the left")
    seg = [round(hav_km(a[1], a[2], b[1], b[2])) for a, b in zip(sts[:-1], sts[1:])]
    return dict(id=c["id"], name=c["name"], country=c["country"], status=c["status"], region=c["region"],
                bbox=[round(float(v), 2) for v in (x0, y0, x1, y1)], north=[round(n, 3) for n in north],
                route_km=sum(seg), seg=seg, stations=stations)


def ground(cid, proj, R, bb, sts):
    x0, y0, x1, y1 = bb
    W, H = (x1 - x0) * PX_PER_KM / 100, (y1 - y0) * PX_PER_KM / 100
    fig = plt.figure(figsize=(W, H), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis("off")
    fig.patch.set_facecolor(WATER)
    lons, lats = [s[1] for s in sts], [s[2] for s in sts]
    m = 8
    ll = box(min(lons) - m, min(lats) - m, max(lons) + m, max(lats) + m)
    rot = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    for g, fc, ec, lw in ((ADM0, LAND, "none", 0), (ADM1, "none", BORDER, 0.6), (ADM0, "none", "#bdbcb5", 0.9)):
        gg = g.clip(ll).to_crs(proj).rotate(rot, origin=(0, 0))
        gg.plot(ax=ax, facecolor=fc, edgecolor=ec, linewidth=lw)
    h = gpd.read_parquet(os.path.join(OUT, "hex", f"{cid}.parquet"))
    h = h[h["density"] >= BINS[0]]
    tf = Transformer.from_crs(4326, proj, always_xy=True)
    v = np.stack([np.asarray(g.exterior.coords)[:6] for g in h.geometry])
    x, y = tf.transform(v[..., 0].ravel(), v[..., 1].ravel())
    v = (np.column_stack([x, y]) @ R.T).reshape(v.shape)
    cls = np.digitize(h["density"].values, BINS) - 1
    for k, col in enumerate(GREYS):
        sel = cls == k
        if sel.any():
            ax.add_collection(PolyCollection(v[sel], facecolors=col, edgecolors=col, linewidths=0.25))
    os.makedirs(os.path.join(OUT, "ground"), exist_ok=True)
    fig.savefig(os.path.join(OUT, "ground", f"{cid}.png"), dpi=100, facecolor=WATER)
    plt.close(fig)


if __name__ == "__main__":
    data = []
    for c in CORRIDORS:
        data.append(corridor(c))
        print("  ", c["id"], data[-1]["bbox"])
    json.dump(dict(radii=RADII, corridors=data), open(os.path.join(OUT, "prisms.json"), "w"), ensure_ascii=False)
    print("wrote prisms.json", os.path.getsize(os.path.join(OUT, "prisms.json")) // 1024, "KB")
