"""Context population: every Kontur cell within 50 km of a corridor's whole route line.

This is background geography for the page's browser-drawn views (the height view
and the two-corridor comparison). It is never counted in any number; the counts
come from the station catchments in popcalc.py.

out/context/<corridor>.parquet: h3, population, density (people/km²). Hexagon
outlines are rebuilt from the H3 index when drawing, which keeps the files small.

Usage: python extract_context.py
"""
import os, sqlite3
import numpy as np
import pandas as pd
import h3
from shapely.geometry import LineString, Point
from pyproj import Transformer
from stations import CORRIDORS
from popcalc import KONTUR_GPKG

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "out", "context")
BUFFER_KM = 50
RES = 8


def buffer_cells(c):
    """H3 cells whose centres fall within BUFFER_KM of the straight-line route."""
    sts = c["stations"]
    lon0, lat0 = np.mean([s[1] for s in sts]), np.mean([s[2] for s in sts])
    proj = f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +units=km +ellps=WGS84"
    fwd = Transformer.from_crs(4326, proj, always_xy=True)
    inv = Transformer.from_crs(proj, 4326, always_xy=True)
    xy = [fwd.transform(s[1], s[2]) for s in sts]
    geom = (LineString(xy) if len(xy) > 1 else Point(xy[0])).buffer(BUFFER_KM, 32)
    ring = [inv.transform(x, y) for x, y in geom.exterior.coords]
    return set(h3.polygon_to_cells(h3.LatLngPoly([(la, lo) for lo, la in ring]), RES))


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    want = {c["id"]: buffer_cells(c) for c in CORRIDORS}
    allcells = set().union(*want.values())
    print(f"{len(allcells):,} candidate cells; scanning Kontur…", flush=True)
    pop = {}
    con = sqlite3.connect(KONTUR_GPKG)
    for h, p in con.execute("SELECT h3, population FROM population"):
        if h in allcells:
            pop[h] = p
    print(f"{len(pop):,} populated cells found", flush=True)
    for c in CORRIDORS:
        cells = [h for h in want[c["id"]] if h in pop]
        df = pd.DataFrame({"h3": cells, "population": [pop[h] for h in cells]})
        df["density"] = df["population"] / np.array([h3.cell_area(h, unit="km^2") for h in cells])
        # sorted, so reruns write identical files and git only sees real changes
        df.sort_values("h3").to_parquet(os.path.join(OUTDIR, f"{c['id']}.parquet"), index=False)
        print(f"  {c['id']:9s} {len(df):7,d} cells  {df['population'].sum()/1e6:6.1f} M within {BUFFER_KM} km of the line", flush=True)


if __name__ == "__main__":
    main()
