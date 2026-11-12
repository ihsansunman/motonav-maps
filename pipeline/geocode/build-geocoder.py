#!/usr/bin/env python3
"""Ülke arama dizini (docs/offline-all-plan.md, O2): OSM PBF -> tek SQLite (FTS4).

Yerleşimler, önemli yerler (POI), sokaklar ve adresler; her kayda ilçe, il ayrıntısı (OSM idari sınırları,
admin_level 4 ve 6). Arama metni normalize edilir (Türkçe harfler katlanır, küçük harf); uygulama sorguyu aynı
kuralla normalize eder (android .../data/OfflineGeocodingProvider.kt, normalizeForSearch). Önemli kayıtlar küçük
docid alır: FTS sonuçları docid sırasıyla döner, LIMIT önce önemlileri getirir.

Çalıştırma (Docker, infra/geocode/build.sh): build-geocoder.py <pbf> <çıktı.sqlite> <ülke kodu> <yapım tarihi>
"""

import math
import sqlite3
import sys
import unicodedata

import osmium
import shapely
from shapely import wkb

# Tür kodu (uygulamada simge/sıralama için) ve önem sırası (küçük = önce).
CITY, TOWN, SUBURB, VILLAGE, QUARTER, HAMLET, POI, MAJOR_POI, STREET, ADDRESS, NATURE = range(11)
PLACE_KINDS = {
    "city": CITY,
    "town": TOWN,
    "suburb": SUBURB,
    "borough": SUBURB,
    "village": VILLAGE,
    "neighbourhood": QUARTER,
    "quarter": QUARTER,
    "hamlet": HAMLET,
    "locality": HAMLET,
    "island": HAMLET,
    "isolated_dwelling": HAMLET,
}
IMPORTANCE = {CITY: 0, TOWN: 1, SUBURB: 2, MAJOR_POI: 2, VILLAGE: 3, QUARTER: 4, POI: 5, HAMLET: 5, STREET: 6, ADDRESS: 7, NATURE: 2}
POI_KEYS = ("amenity", "shop", "tourism", "leisure", "historic", "aeroway", "railway", "office", "craft", "healthcare")
NATURAL = {"water", "peak", "volcano", "beach", "bay", "cape", "spring", "waterfall", "cave_entrance", "glacier", "saddle"}
MAJOR = {("aeroway", "aerodrome"), ("railway", "station"), ("amenity", "university"), ("tourism", "attraction")}
SKIP_AMENITY = {"bench", "waste_basket", "parking_space", "vending_machine", "bicycle_parking", "toilets", "telephone"}
STREET_TYPES = {
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
    "pedestrian", "service", "track", "road", "motorway_link", "trunk_link", "primary_link", "secondary_link",
}
STREET_GRID_DEG = 0.015
# Ters arama için ızgara: 0,01° (~1 km) hücre.
CELL = 100
FOLD = str.maketrans({"ı": "i", "İ": "i", "I": "i", "ç": "c", "ğ": "g", "ö": "o", "ş": "s", "ü": "u"})


def normalize(text):
    """Arama metni: Türkçe katlama, aksan atma, küçük harf; harf/rakam dışı boşluk (uygulamayla aynı kural)."""
    s = unicodedata.normalize("NFKD", text.translate(FOLD).lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).translate(FOLD)
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def cell(lat, lon):
    return int(math.floor(lat * CELL)) * 100000 + int(math.floor(lon * CELL))


def poi_kind(tags):
    nat = tags.get("natural")
    if nat in NATURAL or tags.get("mountain_pass") == "yes":
        return NATURE
    for key in POI_KEYS:
        value = tags.get(key)
        if value and value != "no" and not (key == "amenity" and value in SKIP_AMENITY):
            return MAJOR_POI if (key, value) in MAJOR else POI
    return None


def main(pbf, out, country, built):
    records = []  # (kind, name, name_en, lat, lon, population)
    streets = {}  # norm name -> [(name, lat, lon)]
    admins = {4: [], 6: []}  # admin_level -> [(name, geometry)]
    factory = osmium.geom.WKBFactory()
    fp = (
        osmium.FileProcessor(pbf)
        .with_locations()
        .with_areas(osmium.filter.KeyFilter("boundary", *POI_KEYS, "natural", "place"))
        .with_filter(osmium.filter.KeyFilter("name", "addr:housenumber", "boundary"))
    )
    for obj in fp:
        tags = obj.tags
        name = tags.get("name")
        if obj.is_area():
            if tags.get("boundary") == "administrative" and name and tags.get("admin_level") in ("4", "6"):
                try:
                    admins[int(tags["admin_level"])].append((name, wkb.loads(factory.create_multipolygon(obj), hex=True)))
                except RuntimeError:
                    pass
                continue
            if not name or "highway" in tags:
                continue
            kind = PLACE_KINDS.get(tags.get("place")) if "place" in tags else poi_kind(tags)
            if kind is None:
                continue
            try:
                p = wkb.loads(factory.create_multipolygon(obj), hex=True).representative_point()
            except (RuntimeError, shapely.errors.GEOSException):
                continue
            records.append((kind, name, tags.get("name:en"), p.y, p.x, 0))
        elif obj.is_node():
            loc = obj.location
            if name:
                kind = PLACE_KINDS.get(tags.get("place")) if "place" in tags else poi_kind(tags)
                if kind is not None:
                    pop = tags.get("population", "0")
                    records.append((kind, name, tags.get("name:en"), loc.lat, loc.lon, int(pop) if pop.isdigit() else 0))
                    continue
            if "addr:housenumber" in tags and "addr:street" in tags:
                label = f"{tags['addr:street']} {tags['addr:housenumber']}"
                records.append((ADDRESS, label, None, loc.lat, loc.lon, 0))
        elif obj.is_way():
            if name and tags.get("highway") in STREET_TYPES and len(obj.nodes) > 1:
                mid = obj.nodes[len(obj.nodes) // 2]
                if mid.location.valid():
                    streets.setdefault(normalize(name), []).append((name, mid.lat, mid.lon))
            elif "addr:housenumber" in tags and "addr:street" in tags and obj.is_closed() and obj.nodes[0].location.valid():
                n = obj.nodes[0]
                records.append((ADDRESS, f"{tags['addr:street']} {tags['addr:housenumber']}", None, n.lat, n.lon, 0))

    # Aynı adlı sokak parçaları: aynı ~1,5 km'lik ızgara hücresindekiler tek kayıt (ilk parça noktası).
    for parts in streets.values():
        reps = {}
        for name, lat, lon in parts:
            reps.setdefault((math.floor(lat / STREET_GRID_DEG), math.floor(lon / STREET_GRID_DEG)), (name, lat, lon))
        records += [(STREET, n, None, la, lo, 0) for n, la, lo in reps.values()]
    print(f"records {len(records)}, provinces {len(admins[4])}, districts {len(admins[6])}", flush=True)

    points = shapely.points([(r[4], r[3]) for r in records])
    names = {}
    for level in (6, 4):
        if not admins[level]:
            continue
        tree = shapely.STRtree([g for _, g in admins[level]])
        idx, hit = tree.query(points, predicate="within")
        found = dict(zip(idx.tolist(), hit.tolist()))
        names[level] = {i: admins[level][j][0] for i, j in found.items()}

    order = sorted(range(len(records)), key=lambda i: (IMPORTANCE[records[i][0]], -records[i][5], records[i][1]))
    db = sqlite3.connect(out)
    db.executescript(
        """
        PRAGMA page_size = 4096;
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE places(id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind INTEGER NOT NULL, detail TEXT,
                            lat REAL NOT NULL, lon REAL NOT NULL, cell INTEGER NOT NULL);
        CREATE VIRTUAL TABLE search USING fts4(content="", text, prefix="2,3");
        """
    )
    rows, texts = [], []
    for docid, i in enumerate(order, start=1):
        kind, name, name_en, lat, lon, _ = records[i]
        detail = [n for n in (names.get(6, {}).get(i), names.get(4, {}).get(i)) if n and n != name]
        detail = ", ".join(dict.fromkeys(detail)) or None
        rows.append((docid, name, kind, detail, round(lat, 6), round(lon, 6), cell(lat, lon)))
        text = " ".join(t for t in (name, name_en if name_en and name_en != name else None, detail) if t)
        texts.append((docid, normalize(text)))
    db.executemany("INSERT INTO places VALUES (?,?,?,?,?,?,?)", rows)
    db.executemany("INSERT INTO search(docid, text) VALUES (?,?)", texts)
    db.execute("CREATE INDEX places_cell ON places(cell)")
    db.executemany("INSERT INTO meta VALUES (?,?)", [("country", country), ("built", built), ("schema", "1")])
    db.commit()
    db.execute("INSERT INTO search(search) VALUES ('optimize')")
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"wrote {out}: {len(rows)} places", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:5])
