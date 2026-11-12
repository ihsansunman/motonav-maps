#!/usr/bin/env bash
# monthly.sh çıktısını yayınlar: Release'ler (tr-, tr-provinces-, tr-routing-, tr-search-<tarih>) ve regions.json.
# Aynı gün yeniden çalışırsa var olan Release'e üzerine yazarak yükler. Gerekli: gh (GH_TOKEN), git.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$1" && pwd)
DATE=$(cat "$W/date")
BUILT="${DATE:0:4}-${DATE:4:2}-${DATE:6:2}"
ODBL="Map data © OpenStreetMap contributors, ODbL 1.0 (https://opendatacommons.org/licenses/odbl/)."

release() { # etiket başlık dosyalar...
  local tag=$1 title=$2; shift 2
  gh release view "$tag" >/dev/null 2>&1 || gh release create "$tag" --title "$title" --notes "$ODBL" --latest=false
  gh release upload "$tag" "$@" --clobber
}
release "tr-$DATE" "Türkiye $BUILT" "$W/tr-$DATE.pmtiles"
release "tr-provinces-$DATE" "Türkiye il il ($BUILT)" "$W"/provinces/TR-*.pmtiles
release "tr-routing-$DATE" "Türkiye rota verisi $BUILT (Valhalla 3.9.0)" "$W/tr-routing.tar.gz"
release "tr-search-$DATE" "Türkiye arama dizini $BUILT" "$W/tr-search.sqlite.gz"

python3 "$HERE/update-catalog.py" "$HERE/../regions.json" "$W" "$DATE"
cd "$HERE/.."
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add regions.json
git commit -m "Katalog: aylık veri $BUILT" && git push
