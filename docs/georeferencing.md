# Georeferencing a scheme

A georeferenced scheme gets a transparent overlay on the app's map, so you can see where you
stand on the TP map with GPS. You do this once per scheme, and again only when the scheme's map
PDF changes (the app then shows "overlay may be outdated").

**Result:** a QGIS control-points file `pipeline/georef_points/{scheme_id}.points` committed to
`main`. The weekly workflow (or the push itself) turns it into
`overlays/{scheme_id}.png` + 4 corner coordinates and publishes them. No reinstall is needed.

## What you need

- **QGIS** (free, https://qgis.org), the LTR version is fine.
- **The pipeline set up locally:** `cd pipeline && uv sync`.
- **The scheme id** from the app or from `catalog/cities/<city>.json`, e.g. `surat-tp-57`.

## Steps

1. **Render the map image the overlay will be built from.** This is important: control points
   are pixel positions, so they must be placed on exactly this image.
   ```bash
   cd pipeline
   uv run python -m opennaksha.run --city surat --no-download   # if output/ doesn't exist yet
   uv run python -m opennaksha.georef surat-tp-57 --render-only
   ```
   This downloads the current map PDF from the official URL and writes
   `pipeline/georef_work/surat-tp-57.png` (page 1 rendered at 150 dpi).
   - If the scheme has several map files, or the map is not on page 1, first create
     `pipeline/georef_points/surat-tp-57.json`:
     ```json
     {"file_url": "<the PDF url from the catalog>", "page": 0}
     ```
     `page` counts from 0.
   - **To keep the title block and legend off the map:** add a crop box in pixels of the
     rendered PNG, `[left, top, right, bottom]`. You can read pixel positions in any image
     viewer or in the QGIS Georeferencer status bar:
     ```json
     {"crop": [120, 280, 4900, 3480]}
     ```
     Place control points on the full image as usual; only the published overlay is cropped.

2. **Add a basemap in QGIS.**
   - New project.
   - In the Browser panel, open **XYZ Tiles → OpenStreetMap**. If it's missing, right-click
     **XYZ Tiles → New Connection**, URL `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.
   - Zoom to the scheme's area.
   - Satellite imagery is **not** used: we only use free sources with clear terms.

3. **Open the Georeferencer:** menu **Layer → Georeferencer…**. Then **File → Open Raster…** and
   pick `pipeline/georef_work/surat-tp-57.png`. If asked for a CRS, choose **EPSG:4326**.

4. **Transformation settings** (gear icon):
   - Transformation type: **Linear** or **Helmert** (affine). The pipeline fits an affine
     transform; other types are ignored.
   - Target CRS: **EPSG:4326 - WGS 84** (EPSG:3857 also works).
   - Leave "Load in QGIS when done" ticked if you want a visual check.

5. **Add control points** (Add Point tool):
   - Click a feature on the TP map that you can also identify on OpenStreetMap, then choose
     **From Map Canvas** and click the same spot on the OSM map.
   - Good points: road junctions, bridge ends, railway crossings, the corners of large plots
     along main roads, and canal crossings.
   - Use **at least 4 points, ideally 6–10, spread over the whole sheet** (corners and middle),
     not in one line.
   - Check the residuals in the GCP table. Remove points with residuals much larger than the
     others: they are usually mis-clicks.

6. **Save the points:** **File → Save GCP Points as…** →
   `pipeline/georef_points/surat-tp-57.points`. The file name must be exactly the scheme id.

7. **Optional local check:**
   ```bash
   uv run python -m opennaksha.georef surat-tp-57
   ```
   This prints the 4 corner coordinates and the typical error in metres, and writes
   `pipeline/output/overlays/surat-tp-57.png`. An error of 5–20 m is normal for TP maps.

8. **Publish:**
   ```bash
   git add pipeline/georef_points/surat-tp-57.points
   git commit -m "georef: surat-tp-57"
   git push
   ```
   The **Update catalog** workflow runs automatically on this push. After it finishes, the app
   picks up the overlay on its next update check.

## When the overlay becomes outdated

When a scheme's map PDF changes (new sha256), the overlay is marked `outdated`. The app then
shows: *"This scheme's map was updated. This overlay may be outdated — check the latest PDF."*

To fix it, repeat the steps above. `--render-only` downloads the new PDF. Save over the same
`.points` file and push. The overlay rebuilds because the points file changed.

## How it works (for maintainers)

- **Rendering:** `opennaksha.georef.overlay` renders the PDF page at 150 dpi with pypdfium2. That
  is also GDAL's default, so points placed on the PDF opened directly in QGIS line up too.
- **Fit:** it fits an affine transform from pixels to Web Mercator by least squares.
- **Corners:** it computes where the image corners land. MapLibre draws an `ImageSource` on 4
  corner coordinates using two triangles in Web Mercator, which reproduces an affine transform
  exactly, so the image doesn't need to be warped.
- **PNG:** it downscales to at most 4096 px on the long side, makes near-white pixels
  transparent, reduces to a 128-colour palette and saves an optimized PNG.
- **Overlay record:** it stores `overlay.source_sha256` (the PDF used) and
  `overlay.points_sha256` (the points file used).
  - The pipeline marks the overlay `outdated` when no current map file matches `source_sha256`.
  - It rebuilds whenever the points file changes.
