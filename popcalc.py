"""Population within radius R of each HSR station.

Two sources, same logic:
  hrsl   – Meta/CIESIN High Resolution Settlement Layer, 1 arc-second (~30 m)
           COGs on AWS Open Data (s3://dataforgood-fb-data). No Canada coverage.
  kontur – Kontur Population 2023-11-01, H3 res-8 hexagons (~0.74 km², ~460 m
           edge), global incl. Canada. Built from GHSL + HRSL + Microsoft
           buildings + Copernicus land cover.

For each station and radius we report:
  raw   – everyone whose cell centre is within R of the station
  dedup – same, but a cell is only credited to its *nearest* station on the
          corridor, so overlapping circles (Tokyo/Shinagawa, Taipei/Nangang…)
          aren't double-counted. Corridor totals use dedup.

Usage: python popcalc.py hrsl|kontur [corridor_id ...]   (ids given -> recompute only those)
"""
import json, sys, os
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from stations import CORRIDORS

R_EARTH = 6371.0088
HERE = os.path.dirname(os.path.abspath(__file__))
HRSL_VRT = "/vsicurl/https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt"
KONTUR_GPKG = os.path.join(HERE, "data", "kontur_population_20231101.gpkg")


def hav_km(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(a))


def bbox(lon, lat, r_km, pad=1.02):
    dlat = np.degrees(r_km * pad / R_EARTH)
    dlon = dlat / np.cos(np.radians(lat))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def summarise(pop, lons, lats, st, corridor_sts, radii):
    """pop/lons/lats: 1-D arrays of cell populations and centres near station st."""
    d_self = hav_km(st[1], st[2], lons, lats)
    # distance to every other station on the corridor -> nearest-station flag
    nearest = np.ones_like(d_self, dtype=bool)
    for o in corridor_sts:
        if o is st or hav_km(st[1], st[2], o[1], o[2]) > 2 * max(radii):
            continue
        nearest &= d_self <= hav_km(o[1], o[2], lons, lats)
    out = {}
    for r in radii:
        m = d_self <= r
        out[f"raw_{r}"] = float(pop[m].sum())
        out[f"dedup_{r}"] = float(pop[m & nearest].sum())
    return out


# ---------------------------------------------------------------- sources
def hrsl_points(lon, lat, r_km):
    import rasterio
    from rasterio.windows import from_bounds
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.vrt",
                      GDAL_HTTP_MULTIRANGE="YES", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
                      GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="2",
                      VSI_CACHE="TRUE"):
        with rasterio.open(HRSL_VRT) as ds:
            win = from_bounds(*bbox(lon, lat, r_km), ds.transform).round_offsets().round_lengths()
            a = ds.read(1, window=win, boundless=True, fill_value=np.nan)
            t = ds.window_transform(win)
    rows, cols = np.nonzero(np.isfinite(a) & (a > 0))
    pop = a[rows, cols]
    lons = t.c + (cols + 0.5) * t.a
    lats = t.f + (rows + 0.5) * t.e
    return pop, lons, lats


_kontur_cache = {}
def kontur_points(lon, lat, r_km):
    import pyogrio
    from pyproj import Transformer
    tf = Transformer.from_crs(4326, 3857, always_xy=True)
    x0, y0, x1, y1 = bbox(lon, lat, r_km)
    (X0, X1), (Y0, Y1) = tf.transform([x0, x1], [y0, y1])
    df = pyogrio.read_dataframe(KONTUR_GPKG, bbox=(X0, Y0, X1, Y1), columns=["population"])
    c = df.geometry.centroid
    lons, lats = Transformer.from_crs(3857, 4326, always_xy=True).transform(c.x.values, c.y.values)
    return df["population"].values.astype(float), np.asarray(lons), np.asarray(lats)


def run(source, radii, only=None):
    getpts = {"hrsl": hrsl_points, "kontur": kontur_points}[source]
    rmax = max(radii)
    jobs = [(c, s) for c in CORRIDORS for s in c["stations"] if only is None or c["id"] in only]
    if source == "hrsl":  # HRSL has no Canada coverage
        jobs = [(c, s) for c, s in jobs if c["id"] not in ("ab", "on")
                and not (c["id"] == "cascadia" and s[0] == "Vancouver BC")]

    def work(job):
        c, s = job
        pop, lons, lats = getpts(s[1], s[2], rmax)
        res = summarise(pop, lons, lats, s, c["stations"], radii)
        print(f"  {source} {c['id']:8s} {s[0]:24s} " +
              " ".join(f"{r}km={res[f'raw_{r}']/1e3:8.0f}k" for r in radii), flush=True)
        return dict(corridor=c["id"], station=s[0], lon=s[1], lat=s[2], **res)

    workers = 8 if source == "hrsl" else 4
    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(work, jobs))
    path = os.path.join(HERE, "out", f"pop_{source}.json")
    if only:  # recompute just these corridors and merge into the existing file
        with open(path) as f:
            rows = [r for r in json.load(f)["rows"] if r["corridor"] not in only] + rows
    with open(path, "w") as f:
        json.dump(dict(source=source, radii=radii, rows=rows), f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    src = sys.argv[1]
    radii = [5, 10, 20] if src == "hrsl" else [5, 10, 20, 50]
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    run(src, radii, set(sys.argv[2:]) or None)
