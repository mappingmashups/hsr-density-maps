# hsr-density-maps

Mapping population density around existing and proposed high-speed rail stations.

**Live page: https://mappingmashups.github.io/hsr-density-maps/**

Is North American sprawl the real problem for high-speed rail? Metro populations
along US corridors look competitive with Europe and Asia. This project checks
how many of those people actually live **near the stations**, using one global
population grid and fixed radii (5 / 10 / 20 km, plus 50 km as a metro-scale
reference).

## Setup

```sh
pip install -r requirements.txt
./fetch_data.sh          # Natural Earth outlines: enough to redraw maps from the committed out/hex/
./fetch_data.sh --all    # plus Kontur Population (2.4 GB): needed to recompute populations
```

`out/` holds the computed numbers (JSON/CSV) and the hexagon extract, so you can
redraw everything without the big download. Rendered images in `out/` are
git-ignored; the published copies are WebP files in `docs/`.

## Pipeline

| step | script | output |
|---|---|---|
| Station list (14 corridors, ~130 stops) | `stations.py` | – |
| Population within R of each station | `popcalc.py kontur` · `popcalc.py hrsl` | `out/pop_kontur.json`, `out/pop_hrsl.json` |
| Tables | `summarize.py` | `out/stations.csv`, `out/corridors.csv` |
| Hexagons near stations (for footprints) | `extract_hex.py` (~1 min) | `out/hex/<corridor>.parquet` |
| Same-scale maps | `plot_maps.py` | `out/map_nested.*`, `out/map_{5,10,20,50}km.*` (PNG + SVG) |
| Station footprint atlases | `plot_atlas.py` | `out/atlas/<corridor>.png`, `out/atlas_cities.png` |
| Oblique "population as height" view | `build_prisms.py` | `out/prisms.json`, `out/ground/<corridor>.png` (drawn in the browser) |
| Summary charts | `plot_summary.py` | `out/chart_per_km.png`, `out/chart_centralisation.png` |
| Web page | `build_page.py` (template in `page/template.html`) | `docs/` → GitHub Pages (main branch, `/docs`) |

To recompute one corridor after editing `stations.py`: `python popcalc.py kontur <id>` and
`python popcalc.py hrsl <id>`, then `extract_hex.py`, `summarize.py`, `plot_maps.py`, `plot_atlas.py`, `build_prisms.py`, `plot_summary.py`, `build_page.py`.
Add a line to `LOG` in `build_page.py` for each update; the page shows it as a change log.
Then commit `docs/` (plus any changed code or `out/` data) and push; Pages redeploys automatically.

## Data

* **Kontur Population 2023-11-01** (primary). Global H3 resolution-8 hexagons
  (~0.74 km², ~460 m edge). It's a fusion of GHSL, Meta HRSL, Microsoft
  building footprints and Copernicus land cover. It's free and on S3:
  `geodata-eu-central-1-kontur-public.s3.amazonaws.com/kontur_datasets/kontur_population_20231101.gpkg.gz`
  (2.4 GB gz → 6.7 GB GeoPackage, stored in `data/`, not committed). CC BY 4.0.
* **Meta / CIESIN HRSL** (cross-check). 1 arc-second (~30 m) COGs on AWS Open
  Data (`s3://dataforgood-fb-data/hrsl-cogs/hrsl_general/`). It's read remotely
  through `/vsicurl/` windowed reads, so nothing needs downloading. It has **no
  Canada coverage**, so it can't be the uniform base. Where both datasets
  cover a station they agree within a few percent; see `stations.csv`.
* Natural Earth 10 m admin-0 / admin-1 outlines for the map backgrounds.

The WorldPop stats API and GHSL (JRC, 100 m) would be good alternatives; they
weren't reachable from the environment this was first built in. The 5 km
figures in particular deserve a cross-check against GHSL-POP 100 m.

## Method

* A cell counts for a station if its centre is within R km (haversine).
* **Dedup**: where station circles overlap (Tokyo/Shinagawa, Taipei/Banqiao,
  LA basin, NYC/Newark), each cell is credited only to its *nearest* station on
  the corridor. All corridor totals and map circles use dedup values. Raw
  per-station values are in `stations.csv`.
* Maps: each corridor is in its own azimuthal-equidistant projection centred on
  the corridor and rotated so the route's principal axis is vertical (north
  arrow in each panel; `ROT_OVERRIDE` in `plot_maps.py` forces an angle). 100 km is
  the same length in every panel. Circle **area** is
  proportional to population, and each page says how many people 1 km² of
  circle represents.
* Footprints: dashed rings mark the real radius at map scale. Where rings
  overlap they're split along Voronoi lines (halfway between stations), the same
  rule as the dedup counts (`catchment_lines` in `plot_maps.py`). Atlas discs
  keep each station's full 20 km and mark the split with a dashed line and a
  pale wash. Inside them,
  Kontur hexagons are shaded in four density classes (300 / 1,500 / 5,000 /
  15,000 people per km²); 300 and 1,500 are the GHSL urban-cluster and
  urban-centre cut-offs. `FOOTPRINT` in `plot_maps.py` also has a two-class
  "builtup" option. The Kontur GeoPackage has no spatial index, so
  `extract_hex.py` selects cells by H3 ID instead of by bounding box.

## Caveats

* Planned-route station sites are approximations: city centre or the most-cited
  candidate site. Results at 5 km are sensitive to this. For example, Texas
  Central's Houston terminal is at Northwest Mall, not downtown, and that's
  part of why Houston scores low.
* Windsor–Québec combines the Alto project (Toronto–Québec City) with the
  older Windsor–Toronto proposal. The Toronto–Peterborough–Ottawa alignment
  is assumed.
* SF–LA follows CHSRA Phase 1, San Francisco to Anaheim.
* "Share of 50 km population within 10 km" is size-biased: small isolated
  cities score high automatically. That chart is limited to metros with
  ≥ 2.5 M people within 50 km.
