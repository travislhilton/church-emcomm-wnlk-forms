# Simulator maps and geographic overlays

This emergency communications (EMCOMM) simulator work is part of an independent volunteer project, not an official product or publication of The Church of Jesus Christ of Latter-day Saints.

A community's map dataset sits in its export folder, on the EOC (Emergency Operations Center) laptop only (here, under the git-ignored `secure data/`). It never goes into the repository, the release or the public volunteer portal. [COMMUNITY_SETUP.md](COMMUNITY_SETUP.md) gives the file layout; the invented example, `simulation/example/juniper-plains/simulator/`, has every file. This document describes how an application can use the geographic layers.

## The EOC Message Center and the wall

The EOC server serves the same dataset to its Map tab and the wall display's map tile: on the Message Center's Setup tab set **Map data folder** to the export root (or its `simulator` folder). The server then answers `/api/map/status` and `/map/<file>` from that folder only. No folder, no map; nothing else changes. The renderer is `templates/_shared/emcomm-map.js` (vector boundaries and buildings only; the Map tab can lay one map image over a ward on request, the wall never does).

## Which images can be placed on a map?

Every image listed in `simulator/overlays/manifest.json` has placement metadata. A dataset may hold two kinds:

| Collection | Purpose |
|---|---|
| Map artwork (for example `overlays/source-maps/` or the example's `overlays/maps/`) | Original or drawn map artwork, cropped and placed; inset frames positioned on their own |
| Boundary images (for example `overlays/boundaries/`) | Transparent organization outlines with a faint fill, for engines that need raster images |

An image with no manifest record is not placed on a map. A source map with no usable transform gets no guessed scale and no overlay: record it as an exception in the dataset's own README.

## Choose a layer

Use `simulator/organization_boundaries.geojson` for selectable, filterable territory and `simulator/buildings.geojson` for physical facility markers. Vector boundaries stay sharp when zooming. `organization_locations.geojson` may include label points and locations that are not buildings; inspect `location_kind` and `physical_location_known` before treating an organization marker as a building.

Use an artwork image to inspect the source map, or a transparent boundary image when an engine requires raster images. Load images for the selected organization or visible area rather than displaying them all at once. Overlapping artwork can obscure other layers. Control layer order and opacity in the application.

## Library compatibility

| Mapping library | Image mechanism | Placement values |
|---|---|---|
| Google Maps JavaScript | `google.maps.GroundOverlay` | Image URL (web address) and `google_maps_bounds` |
| Leaflet, with its normal Web Mercator map | `L.imageOverlay` | Image URL and `[[south, west], [north, east]]` |
| MapLibre GL JS, in Mercator view | Image source with a raster layer | Image URL and four corners: northwest, northeast, southeast, southwest, each `[longitude, latitude]` |

The images are north-up in Web Mercator, European Petroleum Survey Group (EPSG) coordinate reference system 3857. Geographic placement bounds and GeoJSON use World Geodetic System 1984 (WGS84), EPSG:4326. GeoJSON arrays are `[longitude, latitude]`; bounds arrays are `[west, south, east, north]`. The manifest's named bounds avoid coordinate-order ambiguity. Do not reproject these prepared images again when placing them in a normal Mercator web map. A different map projection requires an appropriate transform or reprojection.

Resolve `image_path` relative to the export root. In a browser, serve the selected assets from an application-accessible location; a local filesystem path is not an image web address. If assets are served from another origin, configure cross-origin access as required by the chosen library. The geographic bounds, dimensions and opacity belong to the selected image record, not to the uncropped page or organization-wide bounding box.

No mapping-library dependency is part of the forms or the EOC application (repository rule 7): the simulator and the EOC draw with their own canvas renderers.

## Metadata and scale

A manifest record carries the image identifier (`overlay_id`, `map_id`), the organization (`org_id`), the image path, dimensions (`image_width_px`, `image_height_px`), byte size and SHA-256 (Secure Hash Algorithm) checksum, geographic and projected bounds (`google_maps_bounds`, `web_mercator_bounds`), `recommended_opacity`, and a label (`paper_label`). The EOC and the simulator need only `kind`, `overlay_id`, `org_id`, `image_path`, `web_mercator_bounds` and `recommended_opacity`. A dataset may add a `.pgw` world file and a `.prj` projection definition per image for geographic information system (GIS) software, and a map-scale table.

Print scale assumes the original physical page size at 100%. Ground scale changes with latitude and may differ between axes; Web Mercator grid metres are not uniform ground metres. Use geographic coordinates and geodesic calculations for simulator movement, distance and radio-range calculations.

Inset frames have their own transforms and scales. Their printed positions in the parent image should be transparent holes so inset artwork cannot cover an unrelated geographic location; title banners inside a referenced frame likewise. These holes represent obscured source content, not missing organization territory.

## Resolution and verification limits

Keep artwork overlays to about 2048 pixels on the longer side. They are screen overlays, not a multilevel tile pyramid. Prefer vector boundaries at close zoom, or generate higher-resolution tiles from the preserved source documents when detailed artwork is required.

Check every image for dimensions, visible content, file size and checksum, and review sample crops, inset masks and boundary renders. **Live geographic alignment has not yet been tested in Google Maps, Leaflet or MapLibre.** Before relying on a simulator view, compare several recognizable roads and buildings at different zoom levels, verify inset placement separately, and test image opacity and layer ordering. Source-map age and approximate boundaries still limit accuracy.

## Documentation maintenance

When a community's dataset changes, update the dataset's own README beside it (in `secure data/`, never here). Update this repository guide when compatibility, file contracts or verification status changes.

References: [Google Maps ground overlays](https://developers.google.com/maps/documentation/javascript/groundoverlays), [Google Maps GeoJSON data layer](https://developers.google.com/maps/documentation/javascript/datalayer), [Leaflet image overlays](https://leafletjs.com/reference.html#imageoverlay), [MapLibre image sources](https://maplibre.org/maplibre-gl-js/docs/API/classes/ImageSource/).
