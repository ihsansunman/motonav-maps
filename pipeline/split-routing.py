#!/usr/bin/env python3
"""Valhalla döşeme arşivini (valhalla_tiles.tar) ana yollar + il paketlerine böler (docs/routing-split.md).

- <ÜLKE>-routing-base.tar.gz: L0 (otoyol) ve L1 (ana yol) döşemeleri, ülke geneli. Her kullanıcıya iner.
- <il>-routing.tar.gz: ilin sınır kutusuna değen L2 (yerel yol, 0,25°) döşemeleri. Sınırdaki döşeme birden çok
  ilin paketinde olabilir; telefonda aynı klasöre açıldığı için çakışma sorun değildir (aynı dosya).
- routing-parts.json: paket kimliği -> dosya, bayt, sha256 (katalog güncellemesi için).

Kullanım: split-routing.py <valhalla_tiles.tar> <parts.json (il kimliği + bbox)> <çıktı klasörü> [ülke=TR]
"""
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile

L2_SIZE = 0.25  # Valhalla yerel katman döşeme boyutu (derece)
L2_COLUMNS = int(360 / L2_SIZE)


def tile_id(name):
    """'2/000/752/123.gph' -> 752123 (klasör basamakları birleşik kimlik)."""
    return int("".join(name[: -len(".gph")].split("/")[1:]))


def l2_bounds(name):
    row, col = divmod(tile_id(name), L2_COLUMNS)
    west, south = -180 + col * L2_SIZE, -90 + row * L2_SIZE
    return west, south, west + L2_SIZE, south + L2_SIZE


def touches(tile, bbox):
    w, s, e, n = tile
    return e > bbox[0] and w < bbox[2] and n > bbox[1] and s < bbox[3]


def write_pack(path, members):
    """Sıralı, zaman damgası sabit tar.gz (aynı veri aynı sha256)."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in sorted(members):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    with open(path, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(raw.getvalue())
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return {"file": os.path.basename(path), "bytes": os.path.getsize(path), "sha256": digest, "tiles": len(members)}


def main(tar_path, parts_path, out, country="TR"):
    os.makedirs(out, exist_ok=True)
    parts = [p for p in json.load(open(parts_path)) if p.get("bbox")]
    base, local = [], []
    with tarfile.open(tar_path) as tar:
        for m in tar:
            if not m.isfile() or not m.name.endswith(".gph"):
                continue  # index.bin: tile_dir ile gerekmez
            data = tar.extractfile(m).read()
            (local if m.name.startswith("2/") else base).append((m.name, data))
    result = {f"{country}-routing-base": write_pack(os.path.join(out, f"{country}-routing-base.tar.gz"), base)}
    covered = set()
    for p in parts:
        members = [(n, d) for n, d in local if touches(l2_bounds(n), p["bbox"])]
        covered.update(n for n, _ in members)
        result[f"{p['id']}-routing"] = write_pack(os.path.join(out, f"{p['id']}-routing.tar.gz"), members)
    with open(os.path.join(out, "routing-parts.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    missing = len(local) - len(covered)
    print(f"base {result[f'{country}-routing-base']['bytes'] // 10**6} MB, {len(parts)} il, "
          f"il toplamı {sum(v['bytes'] for k, v in result.items() if not k.endswith('-base')) // 10**6} MB, "
          f"hiçbir ile düşmeyen L2 döşemesi {missing}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
