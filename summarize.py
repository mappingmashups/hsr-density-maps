"""Corridor & station summary tables (CSV) from out/pop_*.json."""
import json, csv, os
from stations import CORRIDORS
from popcalc import hav_km
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
K = {(r["corridor"], r["station"]): r for r in json.load(open(f"{OUT}/pop_kontur.json"))["rows"]}
H = {(r["corridor"], r["station"]): r for r in json.load(open(f"{OUT}/pop_hrsl.json"))["rows"]}

with open(f"{OUT}/stations.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["corridor", "station", "lon", "lat", "km_to_next"] +
               [f"kontur_raw_{r}km" for r in (5, 10, 20, 50)] + [f"kontur_dedup_{r}km" for r in (5, 10, 20, 50)] +
               [f"hrsl_raw_{r}km" for r in (5, 10, 20)] + ["share_of_50km_within_10km"])
    for c in CORRIDORS:
        sts = c["stations"]
        for i, s in enumerate(sts):
            k, h = K[(c["id"], s[0])], H.get((c["id"], s[0]), {})
            nxt = round(hav_km(s[1], s[2], sts[i+1][1], sts[i+1][2]), 1) if i + 1 < len(sts) else ""
            w.writerow([c["name"], s[0], s[1], s[2], nxt] + [round(k[f"raw_{r}"]) for r in (5, 10, 20, 50)] +
                       [round(k[f"dedup_{r}"]) for r in (5, 10, 20, 50)] + [round(h[f"raw_{r}"]) if h else "" for r in (5, 10, 20)] +
                       [round(k["raw_10"] / k["raw_50"], 3) if k["raw_50"] else ""])

rows = []
for c in CORRIDORS:
    sts = c["stations"]
    L = sum(hav_km(a[1], a[2], b[1], b[2]) for a, b in zip(sts[:-1], sts[1:]))
    t = {r: sum(K[(c["id"], s[0])][f"dedup_{r}"] for s in sts) for r in (5, 10, 20, 50)}
    rows.append(dict(id=c["id"], corridor=c["name"], region=c["region"], status=c["status"], stations=len(sts),
                     route_km=round(L), **{f"pop_{r}km": round(t[r]) for r in t},
                     **{f"per_km_{r}km": round(t[r] / L) for r in (5, 10, 20)},
                     share_10_of_50=round(t[10] / t[50], 3), share_5_of_50=round(t[5] / t[50], 3)))
with open(f"{OUT}/corridors.csv", "w", newline="") as f:
    w = csv.DictWriter(f, rows[0].keys()); w.writeheader(); w.writerows(rows)
json.dump(rows, open(f"{OUT}/corridors.json", "w"), indent=1, ensure_ascii=False)
for r in sorted(rows, key=lambda r: -r["share_10_of_50"]):
    print(f'{r["corridor"][:34]:34s} {r["route_km"]:5d}km  5k={r["pop_5km"]/1e6:5.1f}M 10k={r["pop_10km"]/1e6:5.1f}M 20k={r["pop_20km"]/1e6:5.1f}M 50k={r["pop_50km"]/1e6:5.1f}M  10/50={r["share_10_of_50"]:.2f} 5/50={r["share_5_of_50"]:.2f}  per-km@10={r["per_km_10km"]}')
