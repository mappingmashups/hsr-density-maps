"""Census metro-area (CBSA) population for US stations: the "baseline" metro figure.

Each US station is placed in its county, the county in its Core-Based Statistical
Area (OMB/Census delineation, July 2023), and the CBSA's population is the sum of
its counties' Vintage 2024 estimates. Where several stations on one corridor fall
in the same CBSA, its population is split evenly between them. A station in a
county outside any CBSA gets that county's own population.

Inputs (data/census/, from ./fetch_data.sh):
  list1_2023.xlsx            CBSA delineation (county → CBSA)
  co-est2024-alldata.csv     county population estimates 2020–2024
  cb_2023_us_county_5m.zip   county outlines (cartographic boundary, 1:5M)

Output: out/msa.json  {corridor id: [per-station record, …]}, US stations only.

Usage: python build_msa.py
"""
import json, os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from stations import CORRIDORS

HERE = os.path.dirname(os.path.abspath(__file__))
CEN = os.path.join(HERE, "data", "census")
OUT = os.path.join(HERE, "out")
YEAR = 2024


def load():
    counties = gpd.read_file(f"zip://{os.path.join(CEN, 'cb_2023_us_county_5m.zip')}")[["GEOID", "NAME", "STUSPS", "geometry"]]
    d = pd.read_excel(os.path.join(CEN, "list1_2023.xlsx"), header=2, dtype=str)
    d = d[d["FIPS State Code"].notna() & d["FIPS County Code"].notna()]
    d["GEOID"] = d["FIPS State Code"].str.zfill(2) + d["FIPS County Code"].str.zfill(3)
    deline = d.set_index("GEOID")[["CBSA Code", "CBSA Title", "Metropolitan/Micropolitan Statistical Area"]]
    e = pd.read_csv(os.path.join(CEN, "co-est2024-alldata.csv"), encoding="latin-1", dtype={"STATE": str, "COUNTY": str})
    e = e[e["SUMLEV"] == 50]
    e["GEOID"] = e["STATE"].str.zfill(2) + e["COUNTY"].str.zfill(3)
    pop = e.set_index("GEOID")[f"POPESTIMATE{YEAR}"]
    return counties, deline, pop


def main():
    counties, deline, pop = load()
    cbsa_pop = deline.join(pop).groupby("CBSA Code")[f"POPESTIMATE{YEAR}"].sum()
    cbsa_counties = deline.reset_index().groupby("CBSA Code")["GEOID"].apply(list)
    out = {}
    for c in CORRIDORS:
        recs = []
        for name, lon, lat in c["stations"]:
            hit = counties[counties.contains(Point(lon, lat))]
            if hit.empty:          # outside the US (e.g. Vancouver BC)
                continue
            g = hit.iloc[0]
            if g.GEOID in deline.index:
                cb = deline.loc[g.GEOID]
                key, title, kind = cb["CBSA Code"], cb["CBSA Title"], cb["Metropolitan/Micropolitan Statistical Area"]
                area_pop, area_counties = int(cbsa_pop[key]), cbsa_counties[key]
            else:
                key, title, kind = f"county-{g.GEOID}", f"{g.NAME} County, {g.STUSPS}", "County (not in a metro area)"
                area_pop, area_counties = int(pop[g.GEOID]), [g.GEOID]
            recs.append(dict(station=name, county=f"{g.NAME} County, {g.STUSPS}", county_fips=g.GEOID,
                             area=key, area_title=title, area_kind=kind, area_pop=area_pop, area_counties=area_counties))
        if not recs:
            continue
        n = pd.Series([r["area"] for r in recs]).value_counts()
        for r in recs:
            r["shared_by"] = int(n[r["area"]])
            r["share"] = round(r["area_pop"] / r["shared_by"])
        out[c["id"]] = recs
        print(f"{c['id']:9s}")
        for r in recs:
            print(f"    {r['station']:18s} {r['area_title'][:44]:44s} {r['area_pop']/1e6:5.2f} M / {r['shared_by']} = {r['share']/1e6:5.2f} M")
    json.dump(dict(year=YEAR, vintage="Vintage 2024 county estimates; CBSA delineation July 2023", corridors=out),
              open(os.path.join(OUT, "msa.json"), "w"), ensure_ascii=False, indent=1)
    print("wrote out/msa.json")


if __name__ == "__main__":
    main()
