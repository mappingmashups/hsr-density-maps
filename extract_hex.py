"""Cache Kontur hexagons within 50 km of any station, one GeoParquet per corridor.

out/hex/<corridor>.parquet: geometry (EPSG:4326 hexagon), population, density
(people/km²), lon/lat of the hex centre. plot_maps.py uses these to draw the
built-up footprint inside each station's real radius.

The Kontur GeoPackage has no spatial index, so bounding-box reads scan the whole
file. Instead, list every H3 res-8 cell within 50 km of each station (h3.grid_disk),
read only the h3 + population columns once, and keep the matches. Hexagon
outlines and areas come from the h3 library.

Usage: python extract_hex.py
"""
import os, sqlite3
import numpy as np
import pandas as pd
import geopandas as gpd
import h3
from shapely.geometry import Polygon
from stations import CORRIDORS
from popcalc import KONTUR_GPKG, hav_km

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "out", "hex")
RMAX = 50
RES = 8
K = int(RMAX / (2 * h3.average_hexagon_edge_length(RES, unit="km") * 0.866)) + 3  # rings to cover RMAX


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    want = {}  # cell -> set of corridor ids
    for c in CORRIDORS:
        for _, lon, lat in c["stations"]:
            for cell in h3.grid_disk(h3.latlng_to_cell(lat, lon, RES), K):
                want.setdefault(cell, set()).add(c["id"])
    print(f"{len(want):,} candidate cells; scanning Kontur…", flush=True)

    con = sqlite3.connect(KONTUR_GPKG)
    rows = []
    for h, p in con.execute("SELECT h3, population FROM population"):
        if h in want:
            rows.append((h, p))
    print(f"{len(rows):,} populated cells found", flush=True)

    df = pd.DataFrame(rows, columns=["h3", "population"])
    ll = np.array([h3.cell_to_latlng(h) for h in df["h3"]])
    df["lat"], df["lon"] = ll[:, 0], ll[:, 1]
    df["density"] = df["population"] / np.array([h3.cell_area(h, unit="km^2") for h in df["h3"]])
    geom = [Polygon([(lo, la) for la, lo in h3.cell_to_boundary(h)]) for h in df["h3"]]
    gdf = gpd.GeoDataFrame(df, geometry=geom, crs=4326)

    for c in CORRIDORS:
        lon = np.array([s[1] for s in c["stations"]]); lat = np.array([s[2] for s in c["stations"]])
        d = np.min([hav_km(lo, la, gdf["lon"].values, gdf["lat"].values) for lo, la in zip(lon, lat)], axis=0)
        sub = gdf[d <= RMAX].copy()
        sub["dist_km"] = d[d <= RMAX]  # distance to the nearest station on this corridor
        sub.to_parquet(os.path.join(OUTDIR, f"{c['id']}.parquet"))
        print(f"  {c['id']:9s} {len(sub):7,d} hexes  {sub['population'].sum()/1e6:6.1f} M within {RMAX} km", flush=True)


if __name__ == "__main__":
    main()
