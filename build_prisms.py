"""Data + ground images for the page's browser-drawn views.

Each corridor is rotated along its principal axis, either left→right (the oblique
"population as height" view) or bottom→top (the side-by-side comparison, matching
the first series of maps). For every whole km from 5 to 50, each station gets the
people in its full circle and the people counted for it (nearest-station rule, as
in the tables). The page draws catchment shapes itself for whatever radius is chosen.

Outputs:
  out/prisms.json            horizontal geometry in rotated km (x right, y "north" = away from viewer)
  out/ground/<cid>.png       land / water / context density (50 km of the route line) in the same coordinates
  out/compare.json           vertical geometry, plus distance along the route for every station
  out/ground_v/<cid>.png     ground images for the vertical layout

Usage: python build_prisms.py
"""
import json, os
import numpy as np
import geopandas as gpd
import pandas as pd
import h3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from shapely.geometry import Point, MultiPoint, box
from pyproj import Transformer
from stations import CORRIDORS
from popcalc import hav_km
from plot_maps import FOOTPRINT, short

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
R_MIN, R_MAX = 5, 50   # catchment radius range offered on the page (km, 1 km steps)
MAX_ROUTE = 0     # longest corridor, set in __main__
PAD = 55          # km of ground shown around the stations
PX_PER_KM = 3     # ground image resolution
LAND, WATER, BORDER = "#efeee9", "#dfe8ed", "#d2d1cb"
BINS, GREYS = FOOTPRINT["density"]
# lighter than the map footprints: this layer is geographic context, not counted data
CONTEXT_GREYS = ["#e4e3dd", "#d2d1cb", "#bab9b3", "#9d9c97"]

POP = {(r["corridor"], r["station"]): r for r in json.load(open(os.path.join(OUT, "pop_kontur.json")))["rows"]}
_msa_path = os.path.join(OUT, "msa.json")
MSA = json.load(open(_msa_path))["corridors"] if os.path.exists(_msa_path) else {}
_proj_path = os.path.join(OUT, "projection.json")
PROJ = json.load(open(_proj_path))["corridors"] if os.path.exists(_proj_path) else {}   # build_projection.py
COUNTIES = gpd.read_file(f"zip://{os.path.join(HERE, 'data', 'census', 'cb_2023_us_county_5m.zip')}")[["GEOID", "NAME", "geometry"]] if MSA else None
NE = os.path.join(HERE, "data", "ne")
ADM0 = gpd.read_file(os.path.join(NE, "ne_10m_admin_0_countries.geojson"))[["geometry"]]
ADM1 = gpd.read_file(os.path.join(NE, "ne_10m_admin_1_states_provinces_lakes.geojson"))[["geometry"]]


def rnd(a, d=2):
    return [[round(float(x), d), round(float(y), d)] for x, y in a]


def corridor(c, orient="h"):
    sts = c["stations"]
    lon0, lat0 = np.mean([s[1] for s in sts]), np.mean([s[2] for s in sts])
    proj = f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +units=km +ellps=WGS84"
    tf = Transformer.from_crs(4326, proj, always_xy=True)
    xy = np.array([tf.transform(s[1], s[2]) for s in sts])
    # rotate so the principal axis points along +x ("h") or +y ("v"), by the smallest rotation
    v = np.linalg.svd(xy - xy.mean(0))[2][0]
    if orient == "h":
        if v[0] < 0:
            v = -v
        phi = -np.degrees(np.arctan2(v[1], v[0]))
    else:
        if v[1] < 0:
            v = -v
        phi = np.degrees(np.arctan2(v[0], v[1]))
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

    # population at every whole km from R_MIN to R_MAX: "p" = counted (each hexagon credited to its
    # nearest station on the corridor), "pr" = everyone in the full circle. The page draws the
    # catchment shapes itself (circle cut halfway to neighbouring stations) for any radius.
    h = pd.read_parquet(os.path.join(OUT, "hex", f"{c['id']}.parquet"), columns=["lon", "lat", "population"])
    D = np.stack([hav_km(s_[1], s_[2], h["lon"].values, h["lat"].values) for s_ in sts], axis=1)
    near, hp = D.argmin(1), h["population"].values
    edges = np.arange(0, R_MAX + 1)                       # 1 km bins; cumulative sum = people within r
    stations = []
    for i, (s_, p) in enumerate(zip(sts, xy)):
        raw = np.cumsum(np.histogram(D[:, i], bins=edges, weights=hp)[0])
        ded = np.cumsum(np.histogram(D[near == i, i], bins=edges, weights=hp[near == i])[0])
        stations.append(dict(name=short(s_[0]), full=s_[0], x=round(float(p[0]), 2), y=round(float(p[1]), 2),
                             p=[int(round(v)) for v in ded[R_MIN - 1:]], pr=[int(round(v)) for v in raw[R_MIN - 1:]]))

    # comparison maps run the full height of the distance chart, so their ground extends above and
    # below by however much longer the longest corridor is (land/water/borders only out there)
    ext = 0.0
    if orient == "v":
        route = sum(hav_km(a[1], a[2], b[1], b[2]) for a, b in zip(sts[:-1], sts[1:]))
        ext = MAX_ROUTE - route + 60
    gb = (x0, y0 - ext, x1, y1 + ext)
    ground(c["id"], proj, R, gb, sts, "ground" if orient == "h" else "ground_v")
    north = (R @ np.array([0.0, 1.0])).tolist()
    if orient == "h":
        print(f"   {c['id']:9s} turn {phi:6.1f}°  north → ({north[0]:+.2f}, {north[1]:+.2f})  {short(sts[0][0]) if xy[0,0] < xy[-1,0] else short(sts[-1][0])} on the left")
    seg = [round(hav_km(a[1], a[2], b[1], b[2])) for a, b in zip(sts[:-1], sts[1:])]
    if c["id"] in PROJ:  # projected growth to 2050 per radius (counted and full circle)
        for st, gp in zip(stations, PROJ[c["id"]]):
            st["g"], st["gr"] = gp["g"], gp["gr"]
    if orient == "v" and c["id"] in MSA:  # census metro areas (build_msa.py) + county outlines
        recs = {r["station"]: r for r in MSA[c["id"]]}
        for st, s_ in zip(stations, sts):
            r = recs.get(s_[0])
            if r:
                st["msa"] = {k: r[k] for k in ("area", "area_title", "area_kind", "area_pop", "shared_by", "share", "county") if k in r}
                # 2050 metro share: the metro's own projection where published (US counties, Hauer et al.),
                # otherwise today's figure × WorldPop's projected growth within 50 km of the station
                if r.get("area_pop2050"):
                    st["msa"]["share2050"] = round(r["area_pop2050"] / r["shared_by"])
                    st["msa"]["proj_source"] = "US county projections, SSP2"
                elif "gr" in st:
                    st["msa"]["share2050"] = round(r["share"] * st["gr"][-1])
                    st["msa"]["proj_source"] = "WorldPop growth within 50 km, SSP2"
        used = {}
        for r in MSA[c["id"]]:
            for f in r["area_counties"]:
                used[f] = r["area"]
        # county outlines only where there are US metro areas (Canada/Australia have none to draw)
        out_c = counties_in_view(proj, R, (x0, y0, x1, y1), sts, used) if used else None
    if orient == "v":  # distance along the route (straight lines between stops) from the first station
        d = np.concatenate([[0], np.cumsum([hav_km(a[1], a[2], b[1], b[2]) for a, b in zip(sts[:-1], sts[1:])])])
        for st, dd in zip(stations, d):
            st["d"] = round(float(dd), 1)
    res = dict(id=c["id"], name=c["name"], country=c["country"], status=c["status"], region=c["region"],
               gbox=[round(float(v), 2) for v in gb],
               bbox=[round(float(v), 2) for v in (x0, y0, x1, y1)], north=[round(n, 3) for n in north],
               route_km=sum(seg), seg=seg, stations=stations)
    if orient == "v" and c["id"] in MSA and out_c:
        res["counties"] = out_c
    return res


def counties_in_view(proj, R, bb, sts, used):
    """US county outlines inside the panel, rotated like the stations. `area` is set for
    counties that belong to a station's metro area (so the page can tint them)."""
    x0, y0, x1, y1 = bb
    lons, lats = [s[1] for s in sts], [s[2] for s in sts]
    m = 6
    g = COUNTIES.cx[min(lons) - m:max(lons) + m, min(lats) - m:max(lats) + m].to_crs(proj)
    g = g.affine_transform([R[0, 0], R[0, 1], R[1, 0], R[1, 1], 0, 0]).to_frame("geometry").join(COUNTIES[["GEOID", "NAME"]])
    g = gpd.GeoDataFrame(g, geometry="geometry")
    g["geometry"] = g.geometry.intersection(box(x0, y0, x1, y1)).simplify(0.25)
    out = []
    for _, r in g[~g.geometry.is_empty].iterrows():
        parts = getattr(r.geometry, "geoms", [r.geometry])
        rings = [rnd(np.asarray(p.exterior.coords), 1) for p in parts if p.geom_type == "Polygon" and p.area > 0.5]
        if rings:
            out.append(dict(fips=r.GEOID, name=r.NAME, area=used.get(r.GEOID), rings=rings))
    return out


def ground(cid, proj, R, bb, sts, folder="ground"):
    x0, y0, x1, y1 = bb
    W, H = (x1 - x0) * PX_PER_KM / 100, (y1 - y0) * PX_PER_KM / 100
    fig = plt.figure(figsize=(W, H), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis("off")
    fig.patch.set_facecolor(WATER)
    lons, lats = [s[1] for s in sts], [s[2] for s in sts]
    m = 8 + (y1 - y0) / 222   # degrees of margin; grows with tall comparison grounds
    ll = box(min(lons) - m, min(lats) - m, max(lons) + m, max(lats) + m)
    rot = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    for g, fc, ec, lw in ((ADM0, LAND, "none", 0), (ADM1, "none", BORDER, 0.6), (ADM0, "none", "#bdbcb5", 0.9)):
        gg = g.clip(ll).to_crs(proj).rotate(rot, origin=(0, 0))
        gg.plot(ax=ax, facecolor=fc, edgecolor=ec, linewidth=lw)
    # context only: every cell within 50 km of the route line (extract_context.py), never counted
    h = pd.read_parquet(os.path.join(OUT, "context", f"{cid}.parquet"))
    h = h[h["density"] >= BINS[0]]
    tf = Transformer.from_crs(4326, proj, always_xy=True)
    v = np.array([[(lo, la) for la, lo in h3.cell_to_boundary(c)[:6]] for c in h["h3"]])
    x, y = tf.transform(v[..., 0].ravel(), v[..., 1].ravel())
    v = (np.column_stack([x, y]) @ R.T).reshape(v.shape)
    cls = np.digitize(h["density"].values, BINS) - 1
    for k, col in enumerate(CONTEXT_GREYS):
        sel = cls == k
        if sel.any():
            ax.add_collection(PolyCollection(v[sel], facecolors=col, edgecolors=col, linewidths=0.25))
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    fig.savefig(os.path.join(OUT, folder, f"{cid}.png"), dpi=100, facecolor=WATER)
    plt.close(fig)


if __name__ == "__main__":
    MAX_ROUTE = max(sum(hav_km(a[1], a[2], b[1], b[2]) for a, b in zip(c["stations"][:-1], c["stations"][1:]))
                    for c in CORRIDORS)
    for orient, name in (("h", "prisms.json"), ("v", "compare.json")):
        data = [corridor(c, orient) for c in CORRIDORS]
        json.dump(dict(r_min=R_MIN, r_max=R_MAX, corridors=data), open(os.path.join(OUT, name), "w"), ensure_ascii=False)
        print("wrote", name, os.path.getsize(os.path.join(OUT, name)) // 1024, "KB")
