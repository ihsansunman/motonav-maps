# MotoNav maps

Offline vector map archives (PMTiles) for the MotoNav app, one file per region. The app reads
[`regions.json`](regions.json) and downloads the selected region from this repository's Releases.

| Region | File | Size | Built |
|---|---|---|---|
| Türkiye (TR) | `tr-20261103.pmtiles` | 1.5 GB | 2026-11-03 |

## Data and license

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available under the
[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).

The archives are regional extracts (bounding box) of the daily [Protomaps](https://protomaps.com) basemap build,
made with the [`pmtiles`](https://github.com/protomaps/go-pmtiles) CLI. No other changes are made to the data.
Applications that display these tiles must show "© OpenStreetMap contributors".

## Adding a region

1. Extract the region (`pmtiles extract <planet build> <id>-<YYYYMMDD>.pmtiles --bbox=<w,s,e,n>`).
2. Create a release tagged `<id>-<YYYYMMDD>` and attach the file (each file must be under 2 GiB).
3. Add an entry to `regions.json` with `bytes` and `sha256` (`shasum -a 256 <file>`).
