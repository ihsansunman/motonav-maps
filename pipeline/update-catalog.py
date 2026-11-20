#!/usr/bin/env python3
"""regions.json'da Türkiye'nin harita (tamamı + iller), rota (tek parça; ana yollar + il il) ve arama girdilerini
aylık çıktıyla günceller.

Kullanım: update-catalog.py <regions.json> <çalışma klasörü> <YYYYMMDD>. Yükseklik ve diğer ülkeler değişmez.
"""
import hashlib
import json
import os
import sys

REPO = "https://github.com/ihsansunman/motonav-maps/releases/download"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entry(path, tag, built):
    name = os.path.basename(path)
    return {"file": name, "url": f"{REPO}/{tag}/{name}", "bytes": os.path.getsize(path), "sha256": sha256(path), "built": built}


def main(catalog_path, work, date):
    built = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    catalog = json.load(open(catalog_path))
    tr = next(c for c in catalog["countries"] if c["id"] == "TR")
    whole = entry(os.path.join(work, f"tr-{date}.pmtiles"), f"tr-{date}", built)
    tr["whole"].update(whole)
    catalog["regions"][0].update(whole)  # 0.4.x uygulamalar (katalog v1)
    parts = json.load(open(os.path.join(work, "provinces", "parts.json")))
    split_path = os.path.join(work, "routing-split", "routing-parts.json")
    split = json.load(open(split_path)) if os.path.exists(split_path) else {}
    split_tag = f"tr-routing-split-{date}"

    def split_entry(pack_id, names):
        s = split[pack_id]
        return {"id": pack_id, "name": names, "file": s["file"], "url": f"{REPO}/{split_tag}/{s['file']}",
                "bytes": s["bytes"], "sha256": s["sha256"], "built": built}

    def with_routing(p):
        out = {**p, "url": f"{REPO}/tr-provinces-{date}/{p['file']}", "built": built}
        rid = f"{p['id']}-routing"
        if rid in split:
            out["routing"] = split_entry(rid, {k: f"{v} rota verisi" if k == "tr" else f"{v} routing data" for k, v in p["name"].items()})
        return out

    tr["parts"] = sorted((with_routing(p) for p in parts), key=lambda p: p["name"]["tr"])
    if "TR-routing-base" in split:
        tr["routing_base"] = split_entry("TR-routing-base", {"tr": "Türkiye ana yollar rota verisi", "en": "Turkey main roads routing data"})
    tr["routing"].update(entry(os.path.join(work, "tr-routing.tar.gz"), f"tr-routing-{date}", built))
    tr["search"].update(entry(os.path.join(work, "tr-search.sqlite.gz"), f"tr-search-{date}", built))
    with open(catalog_path, "w") as f:
        f.write(json.dumps(catalog, ensure_ascii=False, indent=1) + "\n")
    print(f"regions.json: {built}, {len(parts)} il")


if __name__ == "__main__":
    main(*sys.argv[1:4])
