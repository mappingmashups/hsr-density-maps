"""Stand-alone same-scale map of a few corridors for social media: title, five panels in
one row with the distance between every pair of stops, a one-line key and credits. Run after popcalc.py / extract_hex.py.

Usage: python make_social.py   -> out/social_cascadia_europe.(png|svg)
"""
import plot_maps as pm

ORDER = ["cascadia", "fr", "es", "it", "de"]
RADIUS, DENSITY = 20, 800   # same radius and circle scale as the page's default 20 km map

if __name__ == "__main__":
    pm.PER_ROW = len(ORDER)
    pm.draw([RADIUS], DENSITY, "social_cascadia_europe",
            "Cascadia vs. Europe: how far apart are the stops?",
            "Straight-line distance between consecutive high-speed rail stops on the proposed Vancouver–Seattle–Portland line "
            "and four European lines in service.\n"
            f"Circles show people within {RADIUS} km of each stop. All five maps share one scale; each is turned so the line runs top to bottom.",
            order=ORDER, dpi=150, social=True)
