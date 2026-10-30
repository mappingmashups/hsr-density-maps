"""Build the site: page/template.html + out/*.json + out/ images -> docs/ (GitHub Pages).

Re-run after any data or map change, then commit docs/ and push.
Add a line to LOG for each update so readers can see what changed.
"""
import json, os
from PIL import Image
from stations import CORRIDORS
from popcalc import hav_km

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); SITE = os.path.join(HERE, "docs")  # served by GitHub Pages (main branch, /docs)

LOG = [  # newest first
    ("2026-10-30", "Height view: north never points downward any more, so Florida now reads Orlando → Miami and Taiwan reads Kaohsiung → Taipei."),
    ("2026-10-29", "Moved to GitHub Pages, with data credits and a link to the code. Images now ship as WebP."),
    ("2026-10-28", "Height view: mostly east–west routes now keep north up (Osaka on the left of Tokyo, for example); north–south routes still read in the order of their names."),
    ("2026-10-28", "New view: every corridor turned horizontal and tilted, with each station's catchment raised into a block by population."),
    ("2026-10-27", "Overlapping catchments are now split halfway between stations on the maps and in the footprint atlas, matching how residents are counted."),
    ("2026-10-27", "Maps now show the real radius as dashed rings with population density shaded inside. Added station footprint atlases: 20 km discs for every station, all at one scale."),
    ("2026-10-23", "SF–LA now ends at Anaheim (Irvine removed). Map panels rotated so each route runs vertically."),
    ("2026-10-23", "First version: 14 corridors, 5/10/20/50 km radii, Kontur Population with HRSL cross-check."),
]
from stations import MAIN_CITY_STATIONS as CITY

K = {(r["corridor"], r["station"]): r for r in json.load(open(f"{OUT}/pop_kontur.json"))["rows"]}
H = {(r["corridor"], r["station"]): r for r in json.load(open(f"{OUT}/pop_hrsl.json"))["rows"]}
corridors = json.load(open(f"{OUT}/corridors.json"))
region = {c["id"]: c["region"] for c in CORRIDORS}
cname = {c["id"]: c["name"] for c in CORRIDORS}

stations, cities = [], []
for c in CORRIDORS:
    sts = c["stations"]
    for i, s in enumerate(sts):
        k, h = K[(c["id"], s[0])], H.get((c["id"], s[0]))
        nxt = round(hav_km(s[1], s[2], sts[i + 1][1], sts[i + 1][2])) if i + 1 < len(sts) else None
        stations.append(dict(cid=c["id"], station=s[0], next=nxt, **{f"raw_{r}": round(k[f"raw_{r}"]) for r in (5, 10, 20, 50)},
                             dedup_10=round(k["dedup_10"]), hrsl_10=round(h["raw_10"]) if h else None))
        if s[0] in CITY and k["raw_50"] >= 2.5e6:
            cities.append(dict(name=s[0].replace("Zuoying (Kaohsiung)", "Kaohsiung").replace(" Atocha", "").replace(" Sants", "")
                               .replace(" Gare de Lyon", "").replace(" Part-Dieu", "").replace(" Porta Nuova", "").replace(" Centrale", "")
                               .replace(" Termini", "").replace(" BC", ""),
                               corridor=c["name"], region=c["region"], p5=k["raw_5"], p10=k["raw_10"], p50=k["raw_50"],
                               s5=round(k["raw_5"] / k["raw_50"], 4), s10=round(k["raw_10"] / k["raw_50"], 4)))

prisms = json.load(open(f"{OUT}/prisms.json"))
data = dict(updated=LOG[0][0], log=LOG, corridors=corridors, stations=stations, cities=cities, prisms=prisms)
html = open(os.path.join(HERE, "page", "template.html")).read().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
os.makedirs(SITE, exist_ok=True)
open(os.path.join(SITE, "index.html"), "w").write(html)
open(os.path.join(SITE, ".nojekyll"), "w").close()  # serve files as-is on GitHub Pages


def webp(src, dst):
    """Images ship as WebP (q88): visually identical here and ~4x smaller than PNG."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.open(src).convert("RGB").save(dst, quality=88, method=6)


for c in CORRIDORS:
    webp(os.path.join(OUT, "ground", f"{c['id']}.png"), os.path.join(SITE, "ground", f"{c['id']}.webp"))
    webp(os.path.join(OUT, "atlas", f"{c['id']}.png"), os.path.join(SITE, "atlas", f"{c['id']}.webp"))
webp(os.path.join(OUT, "atlas_cities.png"), os.path.join(SITE, "atlas", "atlas_cities.webp"))
for v in ("nested", "5km", "10km", "20km", "50km"):
    webp(os.path.join(OUT, f"map_{v}.png"), os.path.join(SITE, "maps", f"map_{v}.webp"))
print("built", os.path.join(SITE, "index.html"), len(stations), "stations", len(cities), "cities")
