"""Stand-alone image for social media: each high-speed line beside the slower regional trains
along the same corridor, which stop in more towns and feed the fast trains. Same frames, scale
and style as make_social.py, without population circles.

Usage: python make_local.py   -> out/social_fast_slow.(png|svg)
"""
import numpy as np
import plot_maps as pm
from popcalc import hav_km
from local_lines import LOCAL

ORDER = ["cascadia", "de", "es", "it", "fr"]


def spacing_lines():
    out = {}
    for cid in ORDER:
        st = LOCAL[cid]["stations"]
        seg = np.array([hav_km(a[1], a[2], b[1], b[2]) for a, b in zip(st[:-1], st[1:])]) / pm.KM_PER_MI
        who = "Amtrak Cascades today" if cid == "cascadia" else f"regional ({LOCAL[cid]['name']})"
        out[cid] = [f"{who}:", f"{len(st)} stops, avg. {seg.mean():.0f} mi apart"]
    return out


if __name__ == "__main__":
    pm.PER_ROW = len(ORDER)
    pm.MIN_W, pm.GAP = 250, 45
    pm.TITLE_H = 120
    pm.SOCIAL_BAND = 215          # one more credit line than make_social.py
    pm.SOCIAL_CREDIT = ("Population: Kontur 2023 (CC BY 4.0) · Stations: Trainline EU (ODbL) · "
                        "Outlines: Natural Earth · Read more: ")
    pm.draw([20], 800, "social_fast_slow",
            "Fast trains, slow trains: who stops where?",
            "Each high-speed line beside the slower regional trains on the same corridor,\n"
            "which stop in many more towns and feed the fast trains.",
            notes="Regional lines join consecutive stops of the regional-express tier (RE, Regionale Veloce, Media "
                  "Distancia, Rodalies, TER), chaining several services where no single train runs end to end. "
                  "In Cascadia the slower line is today's Amtrak Cascades. Distances are straight-line. "
                  "Grey: people per sq mi within 31 miles (50 km) of the high-speed line. "
                  "All five maps share one scale, each turned so the line runs top to bottom.",
            order=ORDER, dpi=200, social=True, miles=True, extra=spacing_lines(),
            local={cid: LOCAL[cid]["stations"] for cid in ORDER})
