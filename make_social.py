"""Stand-alone same-scale map of a few corridors for social media: title, five panels in
one row with the distance between every pair of stops and train speeds, a one-line key and credits.
Run after popcalc.py / extract_hex.py.

Usage: python make_social.py   -> out/social_cascadia_europe.(png|svg)
"""
import numpy as np
import plot_maps as pm
from popcalc import hav_km

ORDER = ["cascadia", "de", "es", "it", "fr"]
RADIUS, DENSITY = 20, 800   # same radius and circle scale as the page's default 20 km map

# Fastest scheduled end-to-end time (minutes) and top line speed (km/h), checked Nov 2026.
# Average speed = straight-line route length through every mapped stop / fastest time, so it
# runs a little below the usual figure based on track length, the same way for every line.
SPEED = {
    "de": dict(minutes=3 * 60 + 53, top_kmh=300),   # ICE Sprinter Berlin Hbf–München Hbf; VDE 8 at 300 km/h
    "es": dict(minutes=2 * 60 + 30, top_kmh=310),   # non-stop AVE; 310 km/h approved since 2011
    "it": dict(minutes=5 * 60 + 30, top_kmh=300),   # fastest through Frecciarossa/Italo Torino–Napoli (approx.)
    "fr": dict(minutes=3 * 60 + 4, top_kmh=300),    # direct TGV inOui Paris Gare de Lyon–Marseille St-Charles
}
# Cascadia: today's Amtrak Cascades (Vancouver–Seattle ~4 h, Seattle–Portland ~3 h 30, Portland–Eugene
# ~2 h 35, not counting the change of train), 79 mph top; 220 mph planned top speed.
CASCADIA_NOW_MIN, CASCADIA_NOW_TOP_MPH, CASCADIA_PLAN_TOP_MPH = 10 * 60 + 5, 79, 220


def route_mi(cid):
    sts = pm.CORR[cid]["stations"]
    return sum(hav_km(a[1], a[2], b[1], b[2]) for a, b in zip(sts[:-1], sts[1:])) / pm.KM_PER_MI


def hm(minutes):
    return f"{minutes // 60} h {minutes % 60:02d}"


def speed_lines():
    out = {}
    for cid, v in SPEED.items():
        avg = route_mi(cid) / (v["minutes"] / 60)
        out[cid] = [f"fastest train {hm(v['minutes'])}: avg. {avg:.0f} mph",
                    f"top speed {v['top_kmh'] / pm.KM_PER_MI:.0f} mph"]
    avg = route_mi("cascadia") / (CASCADIA_NOW_MIN / 60)
    out["cascadia"] = [f"Amtrak today ~{hm(CASCADIA_NOW_MIN)}: avg. {avg:.0f} mph",
                       f"top speed {CASCADIA_NOW_TOP_MPH} mph today, {CASCADIA_PLAN_TOP_MPH} mph planned"]
    return out


if __name__ == "__main__":
    pm.PER_ROW = len(ORDER)
    pm.MIN_W, pm.GAP = 250, 45   # narrower panels than the page so the image comes out near-square
    pm.TITLE_H = 120             # two extra stats lines (speeds) above each panel
    pm.draw([RADIUS], DENSITY, "social_cascadia_europe",
            "Cascadia vs. Europe: how far apart are the stops?",
            "Straight-line miles between consecutive high-speed rail stops on the proposed\n"
            "Vancouver–Seattle–Portland line and four European lines in service. Circles show people\n"
            f"within {RADIUS / pm.KM_PER_MI:.0f} miles of each stop. All five maps share one scale, turned so the line runs top to bottom.\n"
            "Average speed: fastest scheduled train over the mapped route length.",
            order=ORDER, dpi=200, social=True, miles=True, extra=speed_lines())
