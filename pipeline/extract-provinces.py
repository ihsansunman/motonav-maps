#!/usr/bin/env python3
"""Türkiye arşivinden il il PMTiles keser (docs/offline-maps-plan.md).

Girdi: infra/data/tiles/tr.pmtiles (extract-tr.sh) ve il sınırları (geoBoundaries TUR ADM1, kaynak OSM, CC BY-SA 2.0;
sınırlar yalnızca kesim için kullanılır, yayınlanan döşemeler OSM/ODbL). Çıktı: infra/data/tiles/provinces/TR-xx.pmtiles
ve aynı klasörde parts.json (id, ad, dosya, bayt, sha256, bbox). Kullanım: python3 infra/tiles/extract-provinces.py
[<pmtiles aracı> <Türkiye arşivi> <çıktı klasörü>]  (aylık hat: motonav-maps pipeline/monthly.sh)
"""
import hashlib
import json
import pathlib
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "infra/data"
SRC = DATA / "tiles/tr.pmtiles"
OUT = DATA / "tiles/provinces"
BOUNDS_URL = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/TUR/ADM1/geoBoundaries-TUR-ADM1_simplified.geojson"
BOUNDS = DATA / "regions/tur-adm1.geojson"
PMTILES = DATA / "bin/pmtiles"


def bbox(geom):
    xs, ys = [], []

    def walk(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for x in c:
                walk(x)

    walk(geom["coordinates"])
    return [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    global PMTILES, SRC, OUT, BOUNDS
    if len(sys.argv) == 4:
        PMTILES, SRC, OUT = (pathlib.Path(a) for a in sys.argv[1:4])
        BOUNDS = OUT / "tur-adm1.geojson"
    if not BOUNDS.exists():
        BOUNDS.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(BOUNDS_URL, BOUNDS)
    OUT.mkdir(parents=True, exist_ok=True)
    features = json.loads(BOUNDS.read_text())["features"]
    parts = []
    for f in sorted(features, key=lambda f: f["properties"]["shapeISO"]):
        iso = f["properties"]["shapeISO"]
        name = f["properties"]["shapeName"]
        region = OUT / f"{iso}.geojson"
        region.write_text(json.dumps({"type": "FeatureCollection", "features": [f]}))
        out = OUT / f"{iso}.pmtiles"
        if not out.exists():
            subprocess.run([str(PMTILES), "extract", str(SRC), str(out), f"--region={region}"], check=True, capture_output=True)
        region.unlink()
        parts.append({"id": iso, "name": {"tr": name, "en": name}, "file": out.name, "bytes": out.stat().st_size,
                      "sha256": sha256(out), "bbox": bbox(f["geometry"])})
        print(f"{iso} {name} {out.stat().st_size / 1048576:.0f} MB", flush=True)
    (OUT / "parts.json").write_text(json.dumps(parts, ensure_ascii=False, indent=1))
    print(f"toplam {sum(p['bytes'] for p in parts) / 1073741824:.2f} GB, {len(parts)} il", file=sys.stderr)


if __name__ == "__main__":
    main()
