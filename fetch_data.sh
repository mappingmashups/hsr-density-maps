#!/usr/bin/env bash
# Download the source data into data/ (git-ignored).
#   ./fetch_data.sh         Natural Earth outlines only (~60 MB): enough to redraw the
#                           maps, atlases and height view from the committed out/hex/ extract
#   ./fetch_data.sh --all   also Kontur Population (2.4 GB download, 6.7 GB unzipped):
#                           needed to recompute populations or change stations
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data/ne
NE=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson
for f in ne_10m_admin_0_countries ne_10m_admin_1_states_provinces_lakes ne_10m_lakes; do
  [ -s "data/ne/$f.geojson" ] || curl -fL --retry 3 -o "data/ne/$f.geojson" "$NE/$f.geojson"
done
if [ "${1:-}" = "--all" ]; then
  K=kontur_population_20231101.gpkg
  [ -s "data/$K" ] || {
    curl -fL --retry 5 -C - -o "data/$K.gz" \
      "https://geodata-eu-central-1-kontur-public.s3.amazonaws.com/kontur_datasets/$K.gz"
    gunzip -k "data/$K.gz"
  }
fi
echo "data ready"
