"""Build the site: page/template.html + out/*.json + out/ images -> docs/ (GitHub Pages).

Re-run after any data or map change, then commit docs/ and push.
"""
import datetime, json, os
from PIL import Image
from stations import CORRIDORS
from popcalc import hav_km

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); SITE = os.path.join(HERE, "docs")  # served by GitHub Pages (main branch, /docs)

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
compare = json.load(open(f"{OUT}/compare.json"))
# US county outlines are large, so each corridor's go in their own file, fetched only when shown
os.makedirs(os.path.join(SITE, "counties"), exist_ok=True)
for c in compare["corridors"]:
    if c.get("counties"):
        json.dump(c.pop("counties"), open(os.path.join(SITE, "counties", f"{c['id']}.json"), "w"), separators=(",", ":"))
        c["has_counties"] = True
data = dict(updated=datetime.date.today().isoformat(), corridors=corridors, stations=stations, cities=cities, prisms=prisms, compare=compare)
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
    webp(os.path.join(OUT, "ground_v", f"{c['id']}.png"), os.path.join(SITE, "ground_v", f"{c['id']}.webp"))
    webp(os.path.join(OUT, "atlas", f"{c['id']}.png"), os.path.join(SITE, "atlas", f"{c['id']}.webp"))
webp(os.path.join(OUT, "atlas_cities.png"), os.path.join(SITE, "atlas", "atlas_cities.webp"))
for v in ("nested", "5km", "10km", "20km", "50km"):
    webp(os.path.join(OUT, f"map_{v}.png"), os.path.join(SITE, "maps", f"map_{v}.webp"))
for v in ("social_cascadia_europe", "social_fast_slow"):   # stop-spacing section (make_social.py, make_local.py)
    webp(os.path.join(OUT, f"{v}.png"), os.path.join(SITE, "maps", f"{v}.webp"))
print("built", os.path.join(SITE, "index.html"), len(stations), "stations", len(cities), "cities")
