"""Same-scale corridor maps: straight-line HSR segments + population circles.

Every corridor is drawn in its own azimuthal-equidistant projection (km), then
shelf-packed onto one page in a single matplotlib axes, so 100 km is the same
length everywhere and circle AREA ∝ population everywhere on a page.

Usage: python plot_maps.py            -> out/map_nested.(png|svg), out/map_{5,10,20}km.(png|svg)
"""
import json, os
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from shapely.geometry import box, Point, MultiPoint
from shapely.ops import unary_union, voronoi_diagram
from matplotlib.collections import PolyCollection
from pyproj import Transformer
from stations import CORRIDORS
from popcalc import hav_km

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SRC = "kontur"

# categorical slots 1-3 of the reference palette (validated all-pairs)
REGION_COL = {"North America": "#eb6834", "Australia": "#b8461d", "Europe": "#2a78d6", "Asia": "#1baf7a"}
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#8a8984"
PAGE_BG = "#f6f5f1"   # the web page's background, so images sit on it without a white box
LAND, LAND_EDGE, COUNTRY_EDGE, LINE = "#eeede9", "#ffffff", "#c9c8c2", "#3a3a38"
WATER = "#dfe8ed"   # same water colour as the height view, comparison and atlas

# page order follows stations.CORRIDORS: North America, Australia, Europe, Asia
ORDER = [c["id"] for c in CORRIDORS]
PER_ROW = 4    # panels per row; the page is as wide as the widest row
GAP = 70       # km between panels
MIN_W = 390    # km, narrowest panel
TITLE_H = 75   # km above each panel for its name and stats lines
# The web page shows its own heading, explanation and colour/line/density key, so the images
# carry only what must stay to scale with them: panels, scale bar and circle-size key.
# Set to False for stand-alone images with a title, subtitle and full legend.
WITH_TEXT = False
ROT_OVERRIDE = {}  # corridor id -> rotation in degrees, if the automatic one looks wrong

# Footprint layer: Kontur hexagons inside the real radius, drawn as opaque greys
# beneath the (translucent) population circles. Thresholds in people/km².
# "builtup" uses the GHSL Degree of Urbanisation cut-offs (300 = urban cluster,
# 1,500 = urban centre).
FOOTPRINT = {
    "density": ([300, 1500, 5000, 15000], ["#d3d2cc", "#adaca6", "#7f7e79", "#4d4c49"]),
    "builtup": ([300, 1500], ["#d0cfc9", "#8f8e89"]),
}
RING_STYLE = dict(fc="none", ec="#1d1d1b", lw=0.45, ls=(0, (2.2, 1.6)), alpha=0.85)

with open(os.path.join(OUT, f"pop_{SRC}.json")) as f:
    POP = {(r["corridor"], r["station"]): r for r in json.load(f)["rows"]}
CORR = {c["id"]: c for c in CORRIDORS}

ne = os.path.join(HERE, "data", "ne")
ADM1 = gpd.read_file(os.path.join(ne, "ne_10m_admin_1_states_provinces_lakes.geojson"))[["geometry"]]
ADM0 = gpd.read_file(os.path.join(ne, "ne_10m_admin_0_countries.geojson"))[["geometry"]]
LAKES = gpd.read_file(os.path.join(ne, "ne_10m_lakes.geojson"))[["geometry"]]


def add_radius(cids, r):
    """Counted population (nearest-station rule, as popcalc.py) at any radius up to 50 km,
    from the cached hexagons; stored in POP as dedup_<r> so draw() can use it like the
    precomputed 5 / 10 / 20 / 50 km values. Matches popcalc.py exactly at those radii."""
    for cid in cids:
        sts = CORR[cid]["stations"]
        h = gpd.read_parquet(os.path.join(OUT, "hex", f"{cid}.parquet"))
        d = np.array([hav_km(s[1], s[2], h["lon"].values, h["lat"].values) for s in sts])
        near, dmin = d.argmin(0), d.min(0)
        for i, s in enumerate(sts):
            POP[(cid, s[0])][f"dedup_{r}"] = float(h["population"].values[(near == i) & (dmin <= r)].sum())


def r_km(pop, density):
    """Circle radius (map km) whose area represents `pop` at `density` people/km²."""
    return np.sqrt(max(pop, 0) / (np.pi * density))


def short(name):
    return {"Zuoying (Kaohsiung)": "Kaohsiung", "Paris Gare de Lyon": "Paris",
            "Marseille St-Charles": "Marseille", "Madrid Atocha": "Madrid",
            "Barcelona Sants": "Barcelona", "Lyon Part-Dieu": "Lyon",
            "Milano Centrale": "Milano", "Roma Termini": "Roma", "Napoli Centrale": "Napoli",
            "Torino Porta Nuova": "Torino", "Bologna Centrale": "Bologna",
            "Firenze S.M.N.": "Firenze", "Zaragoza Delicias": "Zaragoza",
            "Lleida Pirineus": "Lleida", "Camp de Tarragona": "Tarragona", "Paris Nord": "Paris",
            "Lille Europe": "Lille", "London St Pancras": "London", "Brussels-Midi": "Brussels",
            "Antwerp Central": "Antwerp", "Rotterdam Centraal": "Rotterdam", "Amsterdam Centraal": "Amsterdam",
            "Chicago Union Station": "Chicago", "Sydney Central": "Sydney", "Melbourne Southern Cross": "Melbourne",
            "Berlin Hbf": "Berlin", "Berlin Südkreuz": "Berlin Südkreuz", "Leipzig Hbf": "Leipzig", "Erfurt Hbf": "Erfurt",
            "Nürnberg Hbf": "Nuremberg", "Ingolstadt Hbf": "Ingolstadt", "München Hbf": "Munich", "Mumbai BKC": "Mumbai",
            "Jakarta Halim": "Jakarta", "Bandung Tegalluar": "Bandung"}.get(name, name)


def build_panel(cid, radii, density, min_h=0, context=False):
    c = CORR[cid]
    sts = c["stations"]
    lon0, lat0 = np.mean([s[1] for s in sts]), np.mean([s[2] for s in sts])
    proj = f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +units=km +ellps=WGS84"
    tf = Transformer.from_crs(4326, proj, always_xy=True)
    xy = np.array([tf.transform(s[1], s[2]) for s in sts])
    # rotate so the route's principal axis is vertical (smallest rotation that does it)
    v = np.linalg.svd(xy - xy.mean(0))[2][0]
    if v[1] < 0:
        v = -v
    phi = np.degrees(np.arctan2(v[0], v[1]))  # CCW rotation (deg) that makes v point straight up
    if cid in ROT_OVERRIDE:
        phi = ROT_OVERRIDE[cid]
    t = np.radians(phi)
    R = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
    xy = xy @ R.T
    rmax = max(r_km(POP[(cid, s[0])][f"dedup_{max(radii)}"], density) for s in sts)
    pad = max(rmax, 25) + 15
    x0, y0 = xy.min(0) - pad
    x1, y1 = xy.max(0) + pad
    if x1 - x0 < MIN_W:  # keep room for the title text; widen symmetrically
        extra = (MIN_W - (x1 - x0)) / 2
        x0, x1 = x0 - extra, x1 + extra
    if y1 - y0 < min_h:  # equal-height frames: extend the map evenly above and below
        extra = (min_h - (y1 - y0)) / 2
        y0, y1 = y0 - extra, y1 + extra
    # background polygons: clip in lon/lat with generous margin, then project + clip exactly
    lons, lats = [s[1] for s in sts], [s[2] for s in sts]
    m = 6
    bb = box(min(lons) - m, min(lats) - m, max(lons) + m, max(lats) + m)
    pbox = box(x0, y0, x1, y1)
    bg = [g.clip(bb).to_crs(proj).rotate(phi, origin=(0, 0)).clip(pbox) for g in (ADM1, ADM0, LAKES)]
    seg = [hav_km(a[1], a[2], b[1], b[2]) for a, b in zip(sts[:-1], sts[1:])]
    if context:   # density along the whole line, trimmed to the frame
        v, d = project_context(cid, tf, R)
        keep = ((v[..., 0] >= x0) & (v[..., 0] <= x1) & (v[..., 1] >= y0) & (v[..., 1] <= y1)).all(1)
        hexes = (v[keep], d[keep])
    else:
        hexes = project_hexes(cid, tf, R, max(radii))
    return dict(c=c, sts=sts, xy=xy, bb=(x0, y0, x1, y1), bg=bg, seg=seg, phi=phi, hexes=hexes)


_HEX = {}
def project_hexes(cid, tf, R, rmax):
    """Hexagons within rmax km of a station on this corridor, as (verts[n,6,2] in rotated km, density[n])."""
    if cid not in _HEX:
        _HEX[cid] = gpd.read_parquet(os.path.join(OUT, "hex", f"{cid}.parquet"))
    h = _HEX[cid]
    h = h[(h["dist_km"] <= rmax) & (h["density"] >= 300)]
    rings = [np.asarray(g.exterior.coords)[:6] for g in h.geometry]  # H3 hexagons: 6 vertices
    v = np.stack(rings) if rings else np.zeros((0, 6, 2))
    x, y = tf.transform(v[..., 0].ravel(), v[..., 1].ravel())
    v = (np.column_stack([x, y]) @ R.T).reshape(v.shape)
    return v, h["density"].values


def project_context(cid, tf, R):
    """Cells within 50 km of the whole route line (out/context, from extract_context.py)
    with at least 300 people/km², as (verts[n,6,2] in rotated km, density[n])."""
    import h3, pandas as pd
    h = pd.read_parquet(os.path.join(OUT, "context", f"{cid}.parquet"))
    h = h[h["density"] >= 300]
    rings = [h3.cell_to_boundary(c)[:6] for c in h["h3"]]   # (lat, lng) pairs
    v = np.array(rings, dtype=float).reshape(-1, 6, 2)[..., ::-1] if rings else np.zeros((0, 6, 2))
    x, y = tf.transform(v[..., 0].ravel(), v[..., 1].ravel())
    v = (np.column_stack([x, y]) @ R.T).reshape(v.shape)
    return v, h["density"].values


def catchment_lines(xy, r):
    """Outline of the union of r-km circles around xy, plus the Voronoi dividing lines
    inside it, each drawn once. Returns a list of LineStrings."""
    circles = unary_union([Point(p).buffer(r, 96) for p in xy])
    lines = [circles.boundary]
    if len(xy) > 1:
        env = box(*(xy.min(0) - 10 * r), *(xy.max(0) + 10 * r))
        edges = voronoi_diagram(MultiPoint([tuple(p) for p in xy]), envelope=env, edges=True)
        lines.append(edges.intersection(circles))
    out = []
    for g in lines:
        for part in getattr(g, "geoms", [g]):
            out.extend(getattr(part, "geoms", [part]))
    return [l for l in out if l.geom_type == "LineString" and not l.is_empty and l.length > 0]


def pack(panels):
    """Pack panels left→right, PER_ROW to a row. Title band above each panel.
    Returns (bottom y, page width), both in km of page space."""
    TITLE = TITLE_H
    x = y = 0.0
    shelf_h = width = 0.0
    for i, p in enumerate(panels):
        x0, y0, x1, y1 = p["bb"]
        w, h = x1 - x0, y1 - y0 + TITLE
        if i and i % PER_ROW == 0:
            x, y, shelf_h = 0.0, y - shelf_h - GAP, 0.0
        p["off"] = (x - x0, y - TITLE - y1)  # shift so panel's top-left sits at (x, y-TITLE)
        p["title_xy"] = (x, y)
        width = max(width, x + w)
        x += w + GAP
        shelf_h = max(shelf_h, h)
    return y - shelf_h, width


def draw(radii, density, fname, title, subtitle, footprint="density", order=None, dpi=300, social=False, miles=False, extra=None, notes=""):
    """social=True: a stand-alone image for social media, with a title band above the panels
    and a one-line key plus credits below them (see make_social.py).
    miles=True (social only): distances, scale bar and density key in miles.
    notes (social only): explanatory text set beside the circle key, below the panels.
    extra: corridor id -> list of further stats lines under each panel's title (e.g. train speeds)."""
    U, ul = (1 / KM_PER_MI, "mi") if miles else (1, "km")
    panels = [build_panel(cid, radii, density) for cid in (order or ORDER)]
    if social:   # every frame as tall as the tallest, padded with more map; density along the whole line
        h = max(p["bb"][3] - p["bb"][1] for p in panels)
        panels = [build_panel(cid, radii, density, min_h=h, context=True) for cid in (order or ORDER)]
    bottom, page_w = pack(panels)
    panels_bottom = bottom
    if social:
        bottom -= SOCIAL_BAND
    W = page_w + (110 if social else 40)   # social: room for station names past the last panel
    top = 270 if WITH_TEXT else 235 if social else 15
    H = -bottom + top + 20  # header room
    scale = 0.0072      # inches per km on the page
    fig = plt.figure(figsize=(W * scale, H * scale))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-20, W - 20)
    ax.set_ylim(bottom - 20, top)
    ax.set_aspect("equal")
    ax.axis("off")
    fs = 7.5

    if social:
        ax.text(0, top - 15, title, fontsize=31, weight="bold", color=INK, va="top")
        ax.text(0, top - 105, subtitle, fontsize=16.5, color=INK2, va="top", linespacing=1.2)
    elif WITH_TEXT:
        ax.text(0, 245, title, fontsize=17, weight="bold", color=INK, va="top")
        ax.text(0, 192, subtitle, fontsize=9.5, color=INK2, va="top", linespacing=1.5)

    rings = sorted(radii, reverse=True)
    alphas = {1: [0.22], 2: [0.1, 0.18], 3: [0.07, 0.12, 0.2]}[len(rings)]
    bins, shade = FOOTPRINT[footprint]

    for p in panels:
        ox, oy = p["off"]
        c, sts, xy = p["c"], p["sts"], p["xy"] + (ox, oy)
        col = REGION_COL[c["region"]]
        # the panel is water; land, then lakes, then country borders on top
        x0, y0, x1, y1 = p["bb"]
        ax.add_patch(plt.Rectangle((x0 + ox, y0 + oy), x1 - x0, y1 - y0, fc=WATER, ec="none", zorder=0.9))
        adm1, adm0, lakes = p["bg"]
        for g, fc, ec, lw, z in ((adm1, LAND, LAND_EDGE, 0.5, 1), (lakes, WATER, "none", 0, 1.05), (adm0, "none", COUNTRY_EDGE, 0.8, 1.1)):
            if len(g):
                g.translate(ox, oy).plot(ax=ax, facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z)
        # route
        ax.plot(xy[:, 0], xy[:, 1], color=LINE, lw=1.1, zorder=3,
                ls="-" if c["status"] == "existing" else (0, (4, 2)) if c["status"] == "building" else (0, (1.5, 1.5)),
                solid_capstyle="round")
        if social:   # every gap labelled, upright, just left of the line (station names sit to the right)
            for (a, b), d in zip(zip(xy[:-1], xy[1:]), p["seg"]):
                mx, my = (a + b) / 2
                ax.text(mx - 9, my, f"{d * U:.0f} {ul}", fontsize=6.6, color=INK, weight="bold", ha="right", va="center",
                        zorder=6.5, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=INK3, lw=0.4, alpha=0.9))
                ax.plot([mx - 8, mx], [my, my], color=INK3, lw=0.5, zorder=6.4)
        else:
          for (a, b), d in zip(zip(xy[:-1], xy[1:]), p["seg"]):
            if d >= 90:
                mx, my = (a + b) / 2
                ang = np.degrees(np.arctan2(b[1] - a[1], b[0] - a[0]))
                if ang > 90: ang -= 180
                if ang < -90: ang += 180
                ax.text(mx, my, f"{d:.0f}", fontsize=5.2, color=INK3, rotation=ang, rotation_mode="anchor",
                        ha="center", va="bottom", zorder=6,
                        bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none", alpha=0.6))
        # circles: biggest ring first, each ring = dedup pop within that radius
        for s, (x, y) in zip(sts, xy):
            pr = POP[(c["id"], s[0])]
            for r, al in zip(rings, alphas):
                rr = r_km(pr[f"dedup_{r}"], density)
                ax.add_patch(Circle((x, y), rr, fc=col, alpha=al, ec="none", zorder=4))
                ax.add_patch(Circle((x, y), rr, fc="none", ec=col, lw=0.9, alpha=0.9, zorder=4.1))
            ax.add_patch(Circle((x, y), 2.2, fc=INK, ec="white", lw=0.4, zorder=5.6))
        # the real-world radius at map scale, split Voronoi-style where circles overlap
        # (matching the nearest-station rule used for the counts)
        for r in ([] if social else rings):   # social image: no dashed catchment outlines
            for line in catchment_lines(xy, r):
                ax.plot(*np.asarray(line.coords).T, color=RING_STYLE["ec"], lw=RING_STYLE["lw"],
                        ls=RING_STYLE["ls"], alpha=RING_STYLE["alpha"], zorder=5.5)
        # footprint: how built-up the land inside the real radius is
        verts, dens = p["hexes"]
        cls = np.digitize(dens, bins) - 1
        for k, col_ in enumerate(shade):
            sel = cls == k
            if sel.any():  # same-colour hairline edge closes the seams between hexagons
                ax.add_collection(PolyCollection(verts[sel] + (ox, oy), facecolors=col_, edgecolors=col_,
                                                 linewidths=0.15, zorder=2, rasterized=True))
        # labels: largest stations first; skip a minor label that would sit on top of one already placed
        main = max(rings)
        placed = []
        order = sorted(zip(sts, xy), key=lambda t: -POP[(c["id"], t[0][0])][f"dedup_{main}"])
        for s, (x, y) in order:
            v = POP[(c["id"], s[0])][f"dedup_{main}"]
            rr = max(r_km(v, density), 4)
            big = v >= 400_000 or s is sts[0] or s is sts[-1]
            lx_, ly_ = x + rr + 3, y
            if any(abs(lx_ - a) < 80 and abs(ly_ - b) < 13 for a, b in placed):
                # try the left side before giving up
                lx_, ly_ = x - rr - 3, y
                if any(abs(lx_ - a) < 80 and abs(ly_ - b) < 13 for a, b in placed):
                    continue
                ha, va = "right", "center"
            else:
                ha, va = "left", "center"
            placed.append((lx_, ly_))
            ax.text(lx_, ly_, short(s[0]),
                    fontsize=fs if big else fs - 1.8, color=INK if big else INK2,
                    weight="bold" if big else "normal", zorder=7, va=va, ha=ha,
                    bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none", alpha=0.55))
        # north arrow (panels are rotated)
        x0, y0, x1, y1 = p["bb"]
        nx, ny = x1 + ox - 22, y1 + oy - 30
        t = np.radians(p["phi"])
        dx, dy = -np.sin(t) * 18, np.cos(t) * 18
        ax.annotate("", xy=(nx + dx, ny + dy), xytext=(nx - dx, ny - dy), zorder=8,
                    arrowprops=dict(arrowstyle="-|>,head_width=0.18,head_length=0.35", color=INK2, lw=0.8))
        ax.text(nx + dx * 1.55, ny + dy * 1.55, "N", fontsize=5.5, color=INK2, ha="center", va="center", zorder=8)
        # title + stats
        tx, ty = p["title_xy"]
        route = sum(p["seg"])
        totals = {r: sum(POP[(c["id"], s[0])][f"dedup_{r}"] for s in sts) for r in radii}
        name = c["name"].replace(" – ", "–") if social else c["name"]
        ax.text(tx, ty, name, fontsize=9.5, weight="bold", color=INK, va="top")
        stat = f"{c['country']} · {c['status']} · {route * U:,.0f} {ul} · {len(sts)} stations"
        ax.text(tx, ty - 26, stat, fontsize=6.4, color=INK2, va="top")
        tot = "   ".join(f"≤{r} km: {totals[r]/1e6:.1f} M" for r in sorted(radii))
        if social:   # stop spacing instead of population totals
            seg = np.array(p["seg"]) * U
            tot = f"avg. {seg.mean():.0f} {ul} between stops ({seg.min():.0f}–{seg.max():.0f})"
        ax.text(tx, ty - 46, tot, fontsize=6.4, color=INK2, va="top")
        for k, line in enumerate((extra or {}).get(c["id"], [])):
            ax.text(tx, ty - 66 - 20 * k, line, fontsize=6.4, color=INK, va="top")

    if social:
        social_key(ax, panels_bottom, page_w, radii, density, miles, notes)
        return save(fig, fname, dpi)
    # legend: scale bar + reference circles, bottom-right
    lx, ly = page_w - 520, bottom + 120
    ax.plot([lx, lx + 100], [ly, ly], color=INK, lw=1.5)
    for t in (0, 50, 100):
        ax.plot([lx + t, lx + t], [ly - 4, ly + 4], color=INK, lw=1)
    ax.text(lx + 50, ly - 10, "100 km (all panels same scale)", fontsize=6.5, ha="center", va="top", color=INK2)
    refs = [1e5, 1e6, 3e6] if density <= 500 else [5e5, 2e6, 5e6] if density <= 1000 else [1e6, 5e6, 15e6]
    cx = lx + 200
    for v in refs:
        rr = r_km(v, density)
        ax.add_patch(Circle((cx + rr, ly + rr - 15), rr, fc="none", ec=INK2, lw=0.7))
        ax.text(cx + rr, ly - 22, f"{v/1e6:g} M" if v >= 1e6 else f"{v/1e3:g}k",
                fontsize=6.5, ha="center", va="top", color=INK2)
        cx += 2 * rr + 18
    if not WITH_TEXT:
        return save(fig, fname, dpi)
    # real radius + footprint key
    fy = ly + 260
    ax.add_patch(Circle((lx + 12, fy), 10, **RING_STYLE))
    ax.text(lx + 30, fy, f"real {' / '.join(str(r) for r in sorted(radii))} km radius; grey = people per km² inside it",
            fontsize=6.5, va="center", color=INK2)
    labels = [f"{b:,}–{bins[i+1]:,}" if i + 1 < len(bins) else f"{b:,}+" for i, b in enumerate(bins)]
    if footprint == "builtup":
        labels = ["300–1,500 (suburban / small town)", "1,500+ (urban)"]
    cx = lx + 12
    for lab, a in zip(labels, shade):
        ax.add_patch(plt.Rectangle((cx - 8, fy - 38), 16, 16, fc=a, ec="none"))
        ax.text(cx + 14, fy - 30, lab, fontsize=6.3, va="center", color=INK2)
        cx += 112 if footprint == "density" else 175
    # line style + region keys
    ky = ly + 110
    for i, (lab, ls) in enumerate([("existing", "-"), ("under construction", (0, (4, 2))), ("planned", (0, (1.5, 1.5)))]):
        ax.plot([lx + i * 170, lx + i * 170 + 40], [ky, ky], color=LINE, lw=1.1, ls=ls)
        ax.text(lx + i * 170 + 48, ky, lab, fontsize=6.5, va="center", color=INK2)
    for i, (lab, col) in enumerate(REGION_COL.items()):   # four regions: 125 km apart so they fit the page
        ax.add_patch(Circle((lx + i * 125 + 12, ky + 40), 10, fc=col, alpha=0.6, ec="none"))
        ax.text(lx + i * 125 + 30, ky + 40, lab, fontsize=6.5, va="center", color=INK2)

    save(fig, fname, dpi)


KM_PER_MI = 1.609344
SOCIAL_BAND = 180   # km of page below the panels for the key, notes and credits
SOCIAL_CREDIT = ("Population: Kontur 2023 (CC BY 4.0) · Outlines: Natural Earth · "
                 "mappingmashups.github.io/hsr-density-maps")


def social_key(ax, y, page_w, radii, density, miles=False, notes=""):
    """Below the panels: scale bar and circle-size key on the left, explanatory notes on
    the right, then a credit line."""
    fs = 7
    ky = y - 95            # centre line of the key row
    x = 0
    bar, unit = (100 * KM_PER_MI, "100 miles") if miles else (100, "100 km")
    ax.plot([x, x + bar], [ky, ky], color=INK, lw=1.5)
    for t in (0, bar):   # end ticks only: the whole bar is the distance
        ax.plot([x + t, x + t], [ky - 4, ky + 4], color=INK, lw=1)
    ax.text(x, ky - 12, f"{unit}, every map\nsame scale", fontsize=fs, ha="left", va="top", color=INK2, linespacing=1.4)
    x += 215
    r = max(radii)
    rlab = f"{r / KM_PER_MI:.0f} miles ({r:.0f} km)" if miles else f"{r:g} km"
    refs = [5e5, 2e6, 5e6] if density <= 1000 else [1e6, 5e6, 15e6]
    ax.text(x, ky + 52, f"People within {rlab}", fontsize=fs, va="bottom", color=INK2)
    base = ky - 40
    for v in refs:
        rr = r_km(v, density)
        ax.add_patch(Circle((x + rr, base + rr), rr, fc="none", ec=INK2, lw=0.7))
        ax.text(x + 2 * rr + 4, base + 2, f"{v/1e6:g} M" if v >= 1e6 else f"{v/1e3:g}k",
                fontsize=fs, ha="left", va="bottom", color=INK2)
        x += 2 * rr + 40
    # notes + credits: wrapped to run from beside the circle key to the right margin
    import textwrap
    nx, fs_n = x + 50, 8.5
    per_line = int((page_w + 70 - nx) / (0.5 * fs_n / 72 / 0.0072))   # ~0.5 em per character; 0.0072 in per km
    paras = [p for p in notes.split("\n") if p] + [SOCIAL_CREDIT]
    text = "\n".join(textwrap.fill(p, per_line) for p in paras)
    ax.text(nx, ky + 58, text, fontsize=fs_n, va="top", color=INK2, linespacing=1.5)


def save(fig, fname, dpi):
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"{fname}.{ext}"), dpi=dpi, facecolor=PAGE_BG)
    plt.close(fig)
    print("wrote", fname)


if __name__ == "__main__":
    note = ("Coloured circle area ∝ residents within the radius of each station (Kontur Population 2023, ~400 m H3 grid); "
            "where circles overlap, each person is counted once, at the nearest station.\n"
            "Dashed rings show the real radius at map scale, split halfway between stations where they overlap (each person counts once, toward the nearest station); the grey inside them is population density.\n"
            "A coloured circle larger than its dashed ring means the area within that radius is denser on average than the circle scale.\n"
            "Each panel is rotated so its route runs vertically (arrow = north). Straight lines join consecutive stops; grey numbers = straight-line km between stops (≥ 90 km shown).")
    draw([5, 10, 20], 800, "map_nested",
         "Who lives near the station?  Population within 5, 10 and 20 km of HSR stops",
         "Nested rings: dark = within 5 km, mid = within 10 km, light = within 20 km.  " + note)
    for r, dens in [(5, 250), (10, 500), (20, 800), (50, 2500)]:
        draw([r], dens, f"map_{r}km", f"Population within {r} km of each HSR station",
             f"Scale: 1 km² of circle = {dens:,} people.  " + note)
