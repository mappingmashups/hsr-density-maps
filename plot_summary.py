"""Summary charts: corridor catchment by radius, and how centralised each big city is around its station."""
import json, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from stations import CORRIDORS
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
REG = {"Europe": "#2a78d6", "North America": "#eb6834", "Asia": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
rows = json.load(open(f"{OUT}/corridors.json"))
plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False})

# 1) small multiples: corridor population (deduped) per route-km, one column per radius
rows_s = sorted(rows, key=lambda r: r["per_km_10km"])
fig, axs = plt.subplots(1, 4, figsize=(12, 5.2), sharey=True)
for ax, (key, lab) in zip(axs, [("per_km_5km", "≤ 5 km"), ("per_km_10km", "≤ 10 km"),
                               ("per_km_20km", "≤ 20 km"), ("pop_50km", "≤ 50 km")]):
    if key == "pop_50km":
        vals = [r["pop_50km"] / r["route_km"] / 1e3 for r in rows_s]
    else:
        vals = [r[key] / 1e3 for r in rows_s]
    ax.barh(range(len(rows_s)), vals, color=[REG[r["region"]] for r in rows_s], height=0.68)
    for i, v in enumerate(vals):
        ax.text(v, i, f" {v:.0f}", va="center", fontsize=7, color=INK2)
    ax.set_title(f"Residents {lab} of a station", fontsize=9, color=INK, loc="left")
    ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.tick_params(length=0)
axs[0].set_yticks(range(len(rows_s)), [r["corridor"] for r in rows_s])
fig.supxlabel("thousand residents per km of route (each resident counted once, at nearest station)", color=INK2, fontsize=8.5)
fig.suptitle("Station catchment population per route-km", x=0.01, ha="left", weight="bold", fontsize=12)
h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in REG.values()]
fig.legend(h, REG.keys(), loc="upper right", ncol=3, frameon=False, fontsize=8)
fig.tight_layout(rect=(0, 0, 1, 0.95))
fig.savefig(f"{OUT}/chart_per_km.png", dpi=200, facecolor="white"); plt.close(fig)

# 2) centralisation: share of the 50 km population that lives within 5 / 10 km, big-city stations
K = json.load(open(f"{OUT}/pop_kontur.json"))["rows"]
reg = {c["id"]: c["region"] for c in CORRIDORS}
CITY = {"Madrid Atocha", "Barcelona Sants", "Zaragoza Delicias", "Paris Gare de Lyon", "Lyon Part-Dieu",
        "Marseille St-Charles", "Torino Porta Nuova", "Milano Centrale", "Bologna Centrale", "Firenze S.M.N.",
        "Roma Termini", "Napoli Centrale", "San Francisco", "San Jose", "Fresno", "Bakersfield", "Los Angeles",
        "Vancouver BC", "Seattle", "Portland", "Dallas", "Houston", "Washington", "Baltimore", "Philadelphia",
        "New York", "Providence", "Boston", "Miami", "Las Vegas", "Calgary", "Edmonton", "Windsor", "London",
        "Toronto", "Ottawa", "Montréal", "Québec City", "Tokyo", "Nagoya", "Kyoto", "Shin-Osaka", "Shizuoka",
        "Hamamatsu", "Seoul", "Daejeon", "Dongdaegu", "Busan", "Taipei", "Taichung", "Zuoying (Kaohsiung)"}
keep = [r for r in K if r["station"] in CITY and r["raw_50"] >= 2.5e6]
keep.sort(key=lambda r: r["raw_10"] / r["raw_50"])
fig, ax = plt.subplots(figsize=(8.5, 0.24 * len(keep) + 1.4))
for i, r in enumerate(keep):
    s5, s10 = r["raw_5"] / r["raw_50"], r["raw_10"] / r["raw_50"]
    col = REG[reg[r["corridor"]]]
    ax.plot([s5, s10], [i, i], color=col, lw=2, alpha=0.5, solid_capstyle="round")
    ax.plot(s5, i, "o", ms=5, mfc="white", mec=col, mew=1.5)
    ax.plot(s10, i, "o", ms=6, color=col)
    ax.text(s10 + 0.012, i, f"{s10:.0%}", va="center", fontsize=6.8, color=INK2)
ax.set_yticks(range(len(keep)), [f'{r["station"].replace("Zuoying (Kaohsiung)","Kaohsiung")}  ({r["raw_50"]/1e6:.1f} M ≤50 km)' for r in keep], fontsize=7.2)
ax.set_xlim(0, 0.8); ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True); ax.tick_params(length=0)
ax.text(0, 1.012, "Metros with ≥ 2.5 M people within 50 km of the station", transform=ax.transAxes, fontsize=8, color=INK2)
ax.set_xlabel("share of the station's 50 km population living within ○ 5 km  /  ● 10 km", fontsize=8)
ax.set_title("How centralised is each city around its main HSR station?", loc="left", weight="bold", fontsize=11)
fig.legend([plt.Line2D([], [], marker="o", ls="", color=c) for c in REG.values()], REG.keys(),
           loc="lower right", bbox_to_anchor=(0.98, 0.06), ncol=1, frameon=False, fontsize=7.5)
fig.tight_layout(); fig.savefig(f"{OUT}/chart_centralisation.png", dpi=200, facecolor="white"); plt.close(fig)
print(len(keep), "cities")
