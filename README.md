# MotoNav maps

Offline data for the MotoNav app, per country. The app reads [`regions.json`](regions.json) and downloads files from this
repository's Releases. With a country's map, the app also downloads that country's routing, search and elevation packs,
so maps, routing, place search and climb all work without internet.

| Pack | Release tag | Content |
|---|---|---|
| Map, whole country | `tr-<date>` | Vector tiles (PMTiles, z0–15) |
| Map, per province | `tr-provinces-<date>` | 81 PMTiles files, cut at province borders |
| Routing | `tr-routing-<date>` | Valhalla 3.9.0 routing tiles (tar, gzip) for on-device routing |
| Search | `tr-search-<date>` | Place search index (SQLite FTS4, gzip): places, POIs, streets, addresses |
| Elevation | `tr-elevation-<date>` | 90 m elevation grid (MNEL v1, gzip) for climb and elevation profile |

## Monthly update

[`.github/workflows/monthly.yml`](.github/workflows/monthly.yml) runs on the 5th of every month. It runs
[`pipeline/monthly.sh`](pipeline/monthly.sh) and then [`pipeline/publish.sh`](pipeline/publish.sh):

1. Downloads the latest Turkey extract from [Geofabrik](https://download.geofabrik.de/europe/turkey.html).
2. Builds the routing and search packs from it.
3. Cuts the map from the latest [Protomaps](https://protomaps.com) daily build.
4. Publishes new Releases and updates `regions.json`.

The app compares each pack's `built` date and offers the update.

The elevation pack doesn't change and isn't rebuilt monthly. A manual run ("Run workflow") without "publish" only builds
the packs and reports their sizes.

The scripts are copied here from the MotoNav source repository (`infra/maps-repo/sync-pipeline.sh`).

## Data and licenses

- **Map, routing and search data:**
  - © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available under the
    [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
  - Applications that use these files must show "© OpenStreetMap contributors".
  - Map tiles are regional extracts of the Protomaps basemap build (`pmtiles extract`), with no other changes.
  - Province borders used only for cutting come from [geoBoundaries](https://www.geoboundaries.org) (TUR ADM1). The
    borders themselves aren't published here.
- **Elevation:**
  - produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided
    under COPERNICUS by the European Union and ESA; all rights reserved.
  - The European Union, ESA and the Copernicus programme don't endorse MotoNav or this use of the data.
