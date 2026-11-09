#!/usr/bin/env bash
# Download the source data into data/ (git-ignored).
#   ./fetch_data.sh         Natural Earth + US census files (~65 MB): enough to redraw the
#                           maps, atlases and height view from the committed out/hex/ extract
#   ./fetch_data.sh --all   also Kontur Population (2.4 GB download, 6.7 GB unzipped):
#                           needed to recompute populations or change stations
#   ./fetch_data.sh --projections
#                           WorldPop 1 km SSP2 projections (4.1 GB) for build_projection.py
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data/ne
NE=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson
for f in ne_10m_admin_0_countries ne_10m_admin_1_states_provinces_lakes ne_10m_lakes; do
  [ -s "data/ne/$f.geojson" ] || curl -fL --retry 3 -o "data/ne/$f.geojson" "$NE/$f.geojson"
done
# US census metro areas (build_msa.py): CBSA delineation, county estimates, county outlines
mkdir -p data/census
CEN=https://www2.census.gov
for u in programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx \
         programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv \
         geo/tiger/GENZ2023/shp/cb_2023_us_county_5m.zip; do
  [ -s "data/census/$(basename "$u")" ] || curl -fL --retry 3 -o "data/census/$(basename "$u")" "$CEN/$u"
done
# Canadian and Australian metro populations (build_msa.py)
mkdir -p data/statcan data/abs
[ -s data/statcan/17100148-eng.zip ] || curl -fL --retry 3 -o data/statcan/17100148-eng.zip \
  https://www150.statcan.gc.ca/n1/tbl/csv/17100148-eng.zip
ABS=https://www.abs.gov.au/statistics/people/population/regional-population/2024-25
for n in 32180DS0003_2001-25 32180DS0004_2001-25; do
  [ -s "data/abs/$n.xlsx" ] || curl -fL --retry 3 -o "data/abs/$n.xlsx" "$ABS/$n.xlsx"
done
if [ "${1:-}" = "--all" ]; then
  K=kontur_population_20231101.gpkg
  [ -s "data/$K" ] || {
    curl -fL --retry 5 -C - -o "data/$K.gz" \
      "https://geodata-eu-central-1-kontur-public.s3.amazonaws.com/kontur_datasets/$K.gz"
    gunzip -k "data/$K.gz"
  }
fi
if [ "${1:-}" = "--projections" ]; then
  mkdir -p data/worldpop
  W=FuturePop_SSP2_1km_v0_2.zip
  [ -s "data/worldpop/$W" ] || curl -fL --retry 5 -C - -o "data/worldpop/$W" \
    "https://data.worldpop.org/repo/prj/FuturePop/SSPs_1km_v0_2/$W"
fi
echo "data ready"
