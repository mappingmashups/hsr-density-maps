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
REGION_COL = {"Europe": "#2a78d6", "North America": "#eb6834", "Asia": "#1baf7a"}
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#8a8984"
LAND, LAND_EDGE, COUNTRY_EDGE, LINE = "#eeede9", "#ffffff", "#c9c8c2", "#3a3a38"

# page order, roughly the comparison you want to read side by side
ORDER = ["ca", "es", "fr", "it", "nec", "on", "cascadia", "tx", "fl", "bw", "ab", "jp", "kr", "tw"]
PAGE_W = 2500  # km of page width before wrapping to the next shelf
GAP = 70       # km between panels
MIN_W = 390    # km, narrowest panel
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
            "Lleida Pirineus": "Lleida", "Camp de Tarragona": "Tarragona"}.get(name, name)


def build_panel(cid, radii, density):
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
    # background polygons: clip in lon/lat with generous margin, then project + clip exactly
    lons, lats = [s[1] for s in sts], [s[2] for s in sts]
    m = 6
    bb = box(min(lons) - m, min(lats) - m, max(lons) + m, max(lats) + m)
    pbox = box(x0, y0, x1, y1)
    bg = [g.clip(bb).to_crs(proj).rotate(phi, origin=(0, 0)).clip(pbox) for g in (ADM1, ADM0)]
    seg = [hav_km(a[1], a[2], b[1], b[2]) for a, b in zip(sts[:-1], sts[1:])]
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
    """Shelf-pack panels left→right, wrapping at PAGE_W. Title band above each panel."""
    TITLE = 75
    x = y = 0.0
    shelf_h = 0.0
    for p in panels:
        x0, y0, x1, y1 = p["bb"]
        w, h = x1 - x0, y1 - y0 + TITLE
        if x > 0 and x + w > PAGE_W:
            x, y, shelf_h = 0.0, y - shelf_h - GAP, 0.0
        p["off"] = (x - x0, y - TITLE - y1)  # shift so panel's top-left sits at (x, y-TITLE)
        p["title_xy"] = (x, y)
        x += w + GAP
        shelf_h = max(shelf_h, h)
    return y - shelf_h


def draw(radii, density, fname, title, subtitle, footprint="density", order=None, dpi=300):
    panels = [build_panel(cid, radii, density) for cid in (order or ORDER)]
    bottom = pack(panels)
    W = PAGE_W + 40
    H = -bottom + 290  # header room
    scale = 0.0072      # inches per km on the page
    fig = plt.figure(figsize=(W * scale, H * scale))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-20, W - 20)
    ax.set_ylim(bottom - 20, 270)
    ax.set_aspect("equal")
    ax.axis("off")
    fs = 7.5

    ax.text(0, 245, title, fontsize=17, weight="bold", color=INK, va="top")
    ax.text(0, 192, subtitle, fontsize=9.5, color=INK2, va="top", linespacing=1.5)

    rings = sorted(radii, reverse=True)
    alphas = {1: [0.22], 2: [0.1, 0.18], 3: [0.07, 0.12, 0.2]}[len(rings)]
    bins, shade = FOOTPRINT[footprint]

    for p in panels:
        ox, oy = p["off"]
        c, sts, xy = p["c"], p["sts"], p["xy"] + (ox, oy)
        col = REGION_COL[c["region"]]
        for g, (fc, ec, lw) in zip(p["bg"], [(LAND, LAND_EDGE, 0.5), ("none", COUNTRY_EDGE, 0.8)]):
            if len(g):
                g = g.translate(ox, oy)
                g.plot(ax=ax, facecolor=fc, edgecolor=ec, linewidth=lw, zorder=1)
        # route
        ax.plot(xy[:, 0], xy[:, 1], color=LINE, lw=1.1, zorder=3,
                ls="-" if c["status"] == "existing" else (0, (4, 2)) if c["status"] == "building" else (0, (1.5, 1.5)),
                solid_capstyle="round")
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
        for r in rings:
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
        ax.text(tx, ty, c["name"], fontsize=9.5, weight="bold", color=INK, va="top")
        stat = f"{c['country']} · {c['status']} · {route:,.0f} km · {len(sts)} stations"
        ax.text(tx, ty - 26, stat, fontsize=6.4, color=INK2, va="top")
        tot = "   ".join(f"≤{r} km: {totals[r]/1e6:.1f} M" for r in sorted(radii))
        ax.text(tx, ty - 46, tot, fontsize=6.4, color=INK2, va="top")

    # legend: scale bar + reference circles, bottom-right
    lx, ly = PAGE_W - 520, bottom + 120
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
    for i, (lab, col) in enumerate(REGION_COL.items()):
        ax.add_patch(Circle((lx + i * 170 + 12, ky + 40), 10, fc=col, alpha=0.6, ec="none"))
        ax.text(lx + i * 170 + 30, ky + 40, lab, fontsize=6.5, va="center", color=INK2)

    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"{fname}.{ext}"), dpi=dpi, facecolor="white")
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
