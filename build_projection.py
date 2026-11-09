"""Projected population growth to 2050 (SSP2) for every station catchment.

WorldPop's 1 km SSP projections (v0.2, SSP2 "middle of the road") are too coarse
to count a 5 km circle directly, so they're used only for *growth*: for each
station and each radius from 5 to 50 km, the ratio of projected 2050 to 2025
population inside the catchment, computed the same two ways as the counts
(full circle, and nearest-station split). The page multiplies today's
high-resolution Kontur counts by these ratios when 2050 is selected.

Input:  data/worldpop/FuturePop_SSP2_1km_v0_2.zip  (from data.worldpop.org; ./fetch_data.sh --projections)
Output: out/projection.json  {"scenario", "base_year", "year", "corridors": {id: [{"g": [...], "gr": [...]}, …]}}
        g  = growth of the counted (nearest-station) population at r = 5…50 km
        gr = growth of the full-circle population at r = 5…50 km

Usage: python build_projection.py
"""
import json, os, re, zipfile
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from stations import CORRIDORS
from popcalc import hav_km, bbox

HERE = os.path.dirname(os.path.abspath(__file__))
WP = os.path.join(HERE, "data", "worldpop")
ZIP = os.path.join(WP, "FuturePop_SSP2_1km_v0_2.zip")
OUT = os.path.join(HERE, "out")
BASE, YEAR, R_MIN, R_MAX = 2025, 2050, 5, 50


def raster_for(year):
    """Path to the year's GeoTIFF, unpacking just that member from the zip on first use."""
    z = zipfile.ZipFile(ZIP)
    names = [n for n in z.namelist() if n.lower().endswith(".tif") and re.search(rf"(?<!\d){year}(?!\d)", n)]
    if len(names) != 1:
        raise SystemExit(f"expected one {year} GeoTIFF in {ZIP}, found {names}")
    dst = os.path.join(WP, os.path.basename(names[0]))
    if not os.path.exists(dst):
        with z.open(names[0]) as src, open(dst, "wb") as f:
            while chunk := src.read(1 << 24):
                f.write(chunk)
    return dst


def cells(ds, sts):
    """Population and centre lon/lat of every 1 km cell within R_MAX of any station."""
    lons, lats = [s[1] for s in sts], [s[2] for s in sts]
    x0 = min(bbox(lo, la, R_MAX)[0] for lo, la in zip(lons, lats)); x1 = max(bbox(lo, la, R_MAX)[2] for lo, la in zip(lons, lats))
    y0 = min(bbox(lo, la, R_MAX)[1] for lo, la in zip(lons, lats)); y1 = max(bbox(lo, la, R_MAX)[3] for lo, la in zip(lons, lats))
    win = from_bounds(x0, y0, x1, y1, ds.transform).round_offsets().round_lengths()
    a = ds.read(1, window=win, boundless=True, fill_value=0).astype("float64")
    if ds.nodata is not None:
        a[a == ds.nodata] = 0
    a[~np.isfinite(a) | (a < 0)] = 0
    t = ds.window_transform(win)
    r, c = np.nonzero(a)
    return a[r, c], t.c + (c + 0.5) * t.a, t.f + (r + 0.5) * t.e


def growth(c, ds_b, ds_y):
    sts = c["stations"]
    edges = np.arange(0, R_MAX + 1)
    res = []
    per_year = []
    for ds in (ds_b, ds_y):
        pop, lon, lat = cells(ds, sts)
        D = np.stack([hav_km(s[1], s[2], lon, lat) for s in sts], axis=1)
        near = D.argmin(1)
        cum = []
        for i in range(len(sts)):
            raw = np.cumsum(np.histogram(D[:, i], bins=edges, weights=pop)[0])
            ded = np.cumsum(np.histogram(D[near == i, i], bins=edges, weights=pop[near == i])[0])
            cum.append((ded[R_MIN - 1:], raw[R_MIN - 1:]))
        per_year.append(cum)
    for (bd, br), (yd, yr) in zip(*per_year):
        with np.errstate(divide="ignore", invalid="ignore"):
            g = np.where(bd > 0, yd / bd, 1.0)
            gr = np.where(br > 0, yr / br, 1.0)
        res.append(dict(g=[round(float(v), 3) for v in g], gr=[round(float(v), 3) for v in gr]))
    return res


def main():
    with rasterio.open(raster_for(BASE)) as ds_b, rasterio.open(raster_for(YEAR)) as ds_y:
        assert ds_b.transform == ds_y.transform, "2025 and 2050 grids differ"
        out = {}
        for c in CORRIDORS:
            out[c["id"]] = growth(c, ds_b, ds_y)
            g10 = [s["g"][10 - R_MIN] for s in out[c["id"]]]
            print(f"  {c['id']:9s} growth at 10 km, {BASE}→{YEAR}: median {np.median(g10):.2f}  range {min(g10):.2f}–{max(g10):.2f}", flush=True)
    json.dump(dict(scenario="SSP2", source="WorldPop Global 1km SSP projections v0.2", base_year=BASE, year=YEAR,
                   r_min=R_MIN, r_max=R_MAX, corridors=out), open(os.path.join(OUT, "projection.json"), "w"))
    print("wrote out/projection.json")


if __name__ == "__main__":
    main()
