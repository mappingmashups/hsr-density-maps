"""Official metro-area population per station: the "baseline" figure people usually quote.

US: Census metro areas (CBSA). Canada: Statistics Canada census metropolitan areas and
agglomerations (CMA/CA, 2025 estimates). Australia: ABS Greater Capital City areas for
Sydney and Melbourne, Significant Urban Areas for the other stops (2025 estimates).
In every country, several stations on one corridor in the same area split it evenly.

US details:

Each US station is placed in its county, the county in its Core-Based Statistical
Area (OMB/Census delineation, July 2023), and the CBSA's population is the sum of
its counties' Vintage 2024 estimates. Where several stations on one corridor fall
in the same CBSA, its population is split evenly between them. A station in a
county outside any CBSA gets that county's own population.

Inputs (data/census/, from ./fetch_data.sh):
  list1_2023.xlsx            CBSA delineation (county → CBSA)
  co-est2024-alldata.csv     county population estimates 2020–2024
  cb_2023_us_county_5m.zip   county outlines (cartographic boundary, 1:5M)

Also data/statcan/17100148-eng.zip and data/abs/32180DS000{3,4}_2001-25.xlsx.
Canadian and Australian stations are matched to their area by name (STATION_AREA below);
there are few enough of them to list, and StatCan's boundary files aren't reachable here.

Output: out/msa.json  {corridor id: [per-station record, …]}; US, Canadian and Australian stations.

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


# Canadian and Australian stations → (source, area name exactly as published)
STATION_AREA = {
    "Vancouver BC": ("statcan", "Vancouver (CMA), British Columbia"),
    "Windsor": ("statcan", "Windsor (CMA), Ontario"), "Chatham": ("statcan", "Chatham-Kent (CA), Ontario"),
    "London": ("statcan", "London (CMA), Ontario"),
    "Kitchener": ("statcan", "Kitchener - Cambridge - Waterloo (CMA), Ontario"), "Guelph": ("statcan", "Guelph (CMA), Ontario"),
    "Toronto": ("statcan", "Toronto (CMA), Ontario"), "Peterborough": ("statcan", "Peterborough (CMA), Ontario"),
    "Ottawa": ("statcan", "Ottawa - Gatineau (CMA), Ontario/Quebec"),
    "Montréal": ("statcan", "Montréal (CMA), Quebec"), "Laval": ("statcan", "Montréal (CMA), Quebec"),
    "Trois-Rivières": ("statcan", "Trois-Rivières (CMA), Quebec"), "Québec City": ("statcan", "Québec (CMA), Quebec"),
    "Calgary": ("statcan", "Calgary (CMA), Alberta"), "Red Deer": ("statcan", "Red Deer (CMA), Alberta"),
    "Edmonton": ("statcan", "Edmonton (CMA), Alberta"),
    "Sydney Central": ("abs_gccsa", "Greater Sydney"), "Campbelltown": ("abs_gccsa", "Greater Sydney"),
    "Southern Highlands": ("abs_sua", "Bowral - Mittagong"), "Canberra": ("abs_sua", "Canberra - Queanbeyan"),
    "Wagga Wagga": ("abs_sua", "Wagga Wagga"), "Albury–Wodonga": ("abs_sua", "Albury - Wodonga"),
    "Shepparton": ("abs_sua", "Shepparton - Mooroopna"),
    "Melbourne Airport": ("abs_gccsa", "Greater Melbourne"), "Melbourne Southern Cross": ("abs_gccsa", "Greater Melbourne"),
}
AREA_KIND = {"statcan": "Statistics Canada metro area (2025)", "abs_gccsa": "ABS Greater Capital City area (2025)",
             "abs_sua": "ABS Significant Urban Area (2025)"}


def other_country_pops():
    """{source: {area name: 2025 population}} for StatCan and ABS."""
    import zipfile
    d = pd.read_csv(zipfile.ZipFile(os.path.join(HERE, "data", "statcan", "17100148-eng.zip")).open("17100148.csv"))
    d = d[(d.REF_DATE == 2025) & (d["Gender"] == "Total - gender") & (d["Age group"] == "All ages")]
    out = {"statcan": dict(zip(d.GEO, d.VALUE))}
    for key, fn, sheet, col in (("abs_gccsa", "32180DS0003_2001-25.xlsx", "Table 4", "GCCSA name"),
                                ("abs_sua", "32180DS0004_2001-25.xlsx", "Table 2", "SUA name")):
        raw = pd.read_excel(os.path.join(HERE, "data", "abs", fn), sheet, header=None)
        h = raw.index[raw.apply(lambda r: r.astype(str).str.contains(col).any(), axis=1)][0]
        ni, yi = raw.iloc[h].astype(str).tolist().index(col), raw.iloc[h - 1].tolist().index(2025)
        out[key] = {str(r[ni]): r[yi] for _, r in raw.iloc[h + 1:].iterrows() if pd.notna(r[yi])}
    return out


def main():
    counties, deline, pop = load()
    other = other_country_pops()
    cbsa_pop = deline.join(pop).groupby("CBSA Code")[f"POPESTIMATE{YEAR}"].sum()
    cbsa_counties = deline.reset_index().groupby("CBSA Code")["GEOID"].apply(list)
    out = {}
    for c in CORRIDORS:
        recs = []
        for name, lon, lat in c["stations"]:
            if name in STATION_AREA:  # Canada / Australia
                src, area = STATION_AREA[name]
                recs.append(dict(station=name, area=f"{src}:{area}", area_title=area.replace(" - ", "–"),
                                 area_kind=AREA_KIND[src], area_pop=int(round(other[src][area])), area_counties=[]))
                continue
            hit = counties[counties.contains(Point(lon, lat))]
            if hit.empty:          # outside the three countries covered
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
    json.dump(dict(year=YEAR, vintage="US: Vintage 2024 county estimates, CBSA delineation July 2023; "
                   "Canada: StatCan table 17-10-0148, 2025; Australia: ABS Regional population 2024–25", corridors=out),
              open(os.path.join(OUT, "msa.json"), "w"), ensure_ascii=False, indent=1)
    print("wrote out/msa.json")


if __name__ == "__main__":
    main()
