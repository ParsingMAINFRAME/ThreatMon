# Map Coverage and Provenance

The world atlas is a geographic index of stored event records that have cited point locations. It is not a global incident census, hazard heatmap, damage estimate, or live warning service.

## Located and Unlocated Records

| Record type | Map behavior | Evidence |
| --- | --- | --- |
| Fetched USGS earthquake | Source-reported point | GeoJSON `geometry.coordinates[0:2]` and attached event citation |
| USGS fixture import | Illustrative demo point | Synthetic local fixture, explicitly marked demo |
| Seeded earthquake and public-health scenarios | Illustrative demo points | Local demo citations; neither is an agency observation |
| CISA KEV catalog entry or cyber demo | No point | Catalog/global context does not establish exploitation geography |
| Asteroid demo | No terrestrial point | Near-Earth space context |
| Other record without `map_location` | No point | Descriptive geography is retained in the register |

The current USGS connector reads the [M2.5+ past-day GeoJSON feed](https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson). Imported snapshots persist after that feed window moves forward. The console therefore does not describe every stored point as an event from the current day.

Coordinates are validated as finite numbers within longitude/latitude ranges. Missing or invalid USGS point geometry fails the import rather than being replaced with a guessed location. For source-reported points, the location references an attached source record; provenance retains the reported coordinates and input origin. Automatic USGS estimates can be preliminary and revised.

## Visual Semantics

Reported points use solid markers; illustrative demo points use outlined diamonds. Selection guides identify the chosen point. The marker legend identifies the styling applied to severity inputs of at least 70; this is a display threshold for a heuristic input, not an official alert level.

Marker size, glow, crosshairs, and color do not encode affected area, impact radius, probability, geographic spread, or population exposure. Demo points remain explicit in the label, legend, and selected-point readout. Native buttons provide keyboard selection; the point index offers alternative controls when markers overlap.

Located/unlocated counts describe the records passed to the map view. Empty map coverage does not mean that no events exist; records without points remain in the event register.

The atlas supports 1×, 2×, and 3× zoom with bounded drag and directional button controls. Land and markers share a transform; marker targets keep a fixed screen size. Zoom focuses the selected point, and the expandable point index offers selection when markers overlap. At 1×, touching the map preserves normal page scrolling.

## Projection

The map and event points use the same equirectangular projection:

```text
x = (longitude + 180) / 360 × 1000
y = (90 − latitude) / 180 × 500
```

The SVG viewBox is `1000 × 500`, with the same 2:1 aspect ratio at different screen sizes. The projection preserves longitude/latitude placement but is not equal-area. Coastline detail is intended for a world overview rather than navigation or local site assessment. The map has no remote tiles, geocoding API, paid service, or runtime map dependency.

## Basemap Attribution

Made with [Natural Earth](https://www.naturalearthdata.com/). Its vector and raster data are [public domain](https://www.naturalearthdata.com/about/terms-of-use/). The application bundles a projected version of the 1:110m land geometry in `frontend/src/lib/world-map.ts`.

| Property | Value |
| --- | --- |
| Dataset | `ne_110m_land.geojson` |
| Repository | [Natural Earth Vector](https://github.com/nvkelso/natural-earth-vector) |
| Pinned commit | `693f11422f4e08d2da4566b854dda53eb7c39fb3` |
| Source file | [Pinned GeoJSON](https://raw.githubusercontent.com/nvkelso/natural-earth-vector/693f11422f4e08d2da4566b854dda53eb7c39fb3/geojson/ne_110m_land.geojson) |
| Source SHA-256 | `9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9` |
| Local transformation | Equirectangular projection, coordinates rounded to 0.1 SVG unit |

Natural Earth is a geographic base layer, not a source for the event claims or point coordinates. Its use implies no publisher endorsement of the application.
