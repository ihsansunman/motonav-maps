#!/usr/bin/env bash
# Aylık veri hattı (MotoNav docs/offline-all-plan.md): Türkiye haritası (il il PMTiles + tamamı), rota (Valhalla)
# ve arama (SQLite FTS4) paketlerini üretir. Yayın: publish.sh. Yükseklik paketi (Copernicus) değişmediği için yok.
# Kullanım: pipeline/monthly.sh <çalışma klasörü>   (GitHub Actions: .github/workflows/monthly.yml)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd)
DATE=${DATE:-$(date -u +%Y%m%d)}
BUILT="${DATE:0:4}-${DATE:4:2}-${DATE:6:2}"
echo "$DATE" > "$W/date"
PMTILES_VERSION=1.31.2 # github.com/protomaps/go-pmtiles/releases
VALHALLA_IMAGE=ghcr.io/valhalla/valhalla:3.9.0 # telefondaki valhalla-mobile ile aynı ana sürüm
BBOX=25.5,35.7,45.0,42.2

step() { echo "::group::$1 ($(date -u +%H:%M))"; }
end() { echo "::endgroup::"; df -h "$W" | tail -1; }

step "OSM (Geofabrik)"
curl -fsSL -o "$W/turkey.osm.pbf" https://download.geofabrik.de/europe/turkey-latest.osm.pbf
ls -l "$W/turkey.osm.pbf"
end

step "Harita: Protomaps derlemesinden Türkiye ve iller"
curl -fsSL "https://github.com/protomaps/go-pmtiles/releases/download/v$PMTILES_VERSION/go-pmtiles_${PMTILES_VERSION}_Linux_x86_64.tar.gz" | tar -xz -C "$W" pmtiles
src=""
for d in "$DATE" $(date -u -d "${BUILT} -1 day" +%Y%m%d) $(date -u -d "${BUILT} -2 day" +%Y%m%d); do
  if curl -fsI "https://build.protomaps.com/$d.pmtiles" >/dev/null; then src="https://build.protomaps.com/$d.pmtiles"; break; fi
done
[ -n "$src" ] || { echo "Protomaps derlemesi bulunamadı" >&2; exit 1; }
echo "Kaynak: $src"
"$W/pmtiles" extract "$src" "$W/tr-$DATE.pmtiles" --bbox="$BBOX" --maxzoom=15
python3 "$HERE/extract-provinces.py" "$W/pmtiles" "$W/tr-$DATE.pmtiles" "$W/provinces"
end

step "Rota: Valhalla döşemeleri"
mkdir -p "$W/valhalla"
docker run --rm -v "$W":/w -w /w/valhalla "$VALHALLA_IMAGE" sh -ec '
  valhalla_build_config --mjolnir-tile-dir /w/valhalla/tiles --mjolnir-tile-extract /w/valhalla/valhalla_tiles.tar \
    --mjolnir-admin /w/valhalla/tiles/admins.sqlite --mjolnir-concurrency "$(nproc)" > valhalla.json
  mkdir -p tiles
  valhalla_build_admins -c valhalla.json /w/turkey.osm.pbf
  valhalla_build_tiles -c valhalla.json /w/turkey.osm.pbf
  valhalla_build_extract -c valhalla.json
'
sudo chown -R "$(id -u)" "$W/valhalla" 2>/dev/null || true
rm -rf "$W/valhalla/tiles"
gzip -9 -c "$W/valhalla/valhalla_tiles.tar" > "$W/tr-routing.tar.gz"
rm -f "$W/valhalla/valhalla_tiles.tar"
end

step "Arama dizini"
docker build -q -t motonav-geocode "$HERE/geocode" >/dev/null
docker run --rm -v "$HERE/geocode":/src:ro -v "$W":/w motonav-geocode \
  python /src/build-geocoder.py /w/turkey.osm.pbf /w/tr-search.sqlite TR "$BUILT"
gzip -9 -c "$W/tr-search.sqlite" > "$W/tr-search.sqlite.gz"
rm -f "$W/tr-search.sqlite"
end

rm -f "$W/turkey.osm.pbf"
{
  echo "### MotoNav veri hattı $BUILT"
  echo "| Dosya | Boyut |"; echo "|---|---|"
  for f in "$W/tr-$DATE.pmtiles" "$W/tr-routing.tar.gz" "$W/tr-search.sqlite.gz"; do
    echo "| $(basename "$f") | $(du -h "$f" | cut -f1) |"
  done
  echo "| il dosyaları ($(ls "$W"/provinces/*.pmtiles | wc -l)) | $(du -ch "$W"/provinces/*.pmtiles | tail -1 | cut -f1) |"
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
