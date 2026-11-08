# OpenNaksha — Complete Build Plan

> A free Android app for viewing Town Planning (TP) scheme maps, Development Plans (DP) and village maps in Gujarat, India.
> Runs on your own Android phone. Data updates automatically every week using free GitHub services — no paid accounts, no server to run, no Play Store needed.
> "OpenNaksha" is a working name — rename freely.

**Instructions for Claude Code:** This file is the single source of truth. Read it fully, then work through the milestones in §11 **in order**. At the end of each milestone, stop, summarize what you built, and wait for the human to approve before continuing. Follow the rules in §2 at all times.

---

## 1. What we are building

**Problem:** Gujarat TP/DP maps are published publicly by government authorities, but they are scattered across many websites as large PDFs, and they change often (new schemes approved, existing schemes modified by government orders). Existing apps (My Estate Point, tpMap) collect them but put features behind paid plans.

**Solution:** A free, no-login Android app that:

1. Shows a catalog of publicly published TP schemes in Gujarat (starting with Surat, then Ahmedabad, Vadodara, Rajkot).
2. Lets the user search, open, download for offline use, and share the official maps.
3. Overlays georeferenced TP maps on a real map with GPS ("where am I on this TP scheme?").
4. **Updates its data automatically** — new and modified schemes appear without reinstalling the app.
5. Always links back to the official government source.

**How it works (no server of our own):**

```
┌────────────────────┐   weekly, automatic   ┌───────────────────────────┐
│ Government portals │ ────────────────────▶ │ GitHub Actions            │
│ SMC, AMC, AUDA ... │                       │ runs pipeline/ (Python)   │
└────────────────────┘                       │ scrape → diff → catalog   │
          ▲                                  └─────────────┬─────────────┘
          │                                                │ commits to `catalog` branch
          │                                                ▼
          │                                  ┌───────────────────────────┐
          │                                  │ GitHub Pages (free static)│
          │                                  │ catalog/*.json            │
          │                                  │ overlays/*.png            │
          │                                  └─────────────┬─────────────┘
          │                                                │ app checks on launch
          │  PDFs downloaded directly                      ▼
          │  from official URLs              ┌───────────────────────────┐
          └───────────────────────────────── │ Android app on the phone  │
                                             │ bundled catalog = fallback│
                                             └───────────────────────────┘
```

- **GitHub Actions** runs the Python scraper on a weekly schedule (and on demand). The human's PC does not need to be on.
- The scraper compares results with the previous catalog, records what's new/changed, and publishes the catalog to **GitHub Pages**.
- The app downloads the latest catalog on launch (only if it changed). If offline or the download fails, it uses the last downloaded copy, or the copy bundled in the APK.
- Map PDFs are always downloaded **directly from the official government URLs**, so new maps are available as soon as they appear in the catalog.
- Overlay images (for GPS on map) are also published on GitHub Pages, so new overlays arrive without reinstalling.
- The app only needs reinstalling when **features** change, never for data.

**Not included (for now):** iOS, accounts, payments, Play Store publishing, hosting 7/12 land records (link out instead).

---

## 2. Rules (must always follow)

- **Never invent government URLs, scheme numbers, or data.** Only use what was actually found on source sites. If unsure, mark it unknown and ask the human.
- Only scrape publicly accessible pages. Respect `robots.txt`, max 1 request/second per host, use timeouts and retries with backoff. Never bypass logins or CAPTCHAs.
- Be gentle on government servers: on scheduled runs, check files with HEAD requests (ETag / Last-Modified / Content-Length) and only download a file when it is new or appears changed.
- No paid services or APIs. No Google Maps SDK. Ask before adding any dependency that needs an account or could cost money.
- No tracking, analytics, or ads.
- Every scheme in the app must show its official source link, and the disclaimer in §7 must be present.
- All UI text goes in `strings.xml` (English + Gujarati). No hardcoded UI text.
- Tests must not hit the live network — use saved HTML fixtures.
- Secrets (if any) only via environment variables / GitHub secrets. Never commit credentials.
- Keep a log of decisions in `docs/decisions.md` (date, decision, reason).
- Small, focused git commits with clear messages.

---

## 3. Prerequisites (human sets these up)

On the computer:

- **Android Studio** (latest stable) — includes the Android SDK and `adb`.
- **JDK 17** (bundled with Android Studio is fine).
- **Python 3.12** and **uv** (`pip install uv`).
- **Git**.
- **QGIS** (free) — only needed for georeferencing (Milestone 5).

Online:

- A free **GitHub account** (needed from Milestone 4). A **public** repository is recommended: GitHub Actions minutes are free for public repos and GitHub Pages works on the free plan. (Private repos have a limited monthly minute allowance and Pages on private repos needs a paid plan — ask the human which they prefer.)

On the phone:

- Android 8.0 or newer.
- Developer options enabled (see §9).

---

## 4. Repository layout

```
/
├── PLAN.md                    # this file
├── README.md
├── docs/
│   ├── sources.md             # findings about each government site (Milestone 1)
│   ├── catalog-schema.md      # JSON schema documentation
│   ├── georeferencing.md      # how to georeference a scheme
│   ├── updates.md             # how automatic updates work + troubleshooting
│   └── decisions.md
├── pipeline/
│   ├── pyproject.toml
│   ├── opennaksha/
│   │   ├── scrapers/
│   │   │   ├── base.py        # BaseScraper interface
│   │   │   ├── surat_smc.py
│   │   │   └── ...            # one file per authority
│   │   ├── models.py          # pydantic models matching the catalog schema
│   │   ├── catalog.py         # builds catalog JSON
│   │   ├── diff.py            # compares with previous catalog, builds changes
│   │   ├── run.py             # CLI entry point
│   │   └── georef/
│   │       └── overlay.py     # PDF + control points → overlay PNG + corner coords
│   ├── georef_points/         # QGIS .points files, one per scheme (committed)
│   ├── fixtures/              # saved HTML for tests
│   └── tests/
├── scripts/
│   ├── sync_assets.sh         # copies latest catalog into android assets
│   └── sync_assets.ps1        # Windows version
├── .github/workflows/
│   ├── update-catalog.yml     # weekly scrape + publish
│   └── ci.yml                 # lint + tests on push/PR
└── android/
    └── (Gradle project, see §8)
```

**Branches**

- `main` — all code.
- `catalog` — **only generated data** (`catalog/`, `overlays/`). Written by GitHub Actions. GitHub Pages serves this branch. Its git history is a free, permanent record of every change to every scheme.

Published URLs (replace `<user>` and `<repo>`):

```
https://<user>.github.io/<repo>/catalog/index.json
https://<user>.github.io/<repo>/catalog/cities/{city_id}.json
https://<user>.github.io/<repo>/catalog/changes.json
https://<user>.github.io/<repo>/overlays/{scheme_id}.png
```

The base URL is set in one place in the Android app (`BuildConfig.CATALOG_BASE_URL`, configured in Gradle).

---

## 5. Data model (catalog)

Files produced by the pipeline (in `pipeline/output/`, then published to the `catalog` branch):

- `catalog/index.json` — schema version, generation time, list of cities with counts
- `catalog/cities/{city_id}.json` — all schemes for one city
- `catalog/changes.json` — what changed in recent runs (last 20 runs)
- `overlays/{scheme_id}.png` — georeferenced overlay images

**index.json**

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-15T02:00:00Z",
  "cities": [
    { "id": "surat", "name_en": "Surat", "name_gu": "સુરત", "scheme_count": 0, "updated_at": "2026-11-15T02:00:00Z" }
  ]
}
```

**Scheme record** (inside `cities/{city_id}.json`):

```json
{
  "id": "surat-tp-57",
  "city_id": "surat",
  "authority": "SMC",
  "scheme_type": "TP",
  "scheme_no": "57",
  "name_en": "Pandesara",
  "name_gu": "પાંડેસરા",
  "status": "preliminary",
  "status_date": "2024-03-12",
  "source_page_url": "https://...",
  "files": [
    {
      "kind": "map",
      "title": "Preliminary scheme map",
      "url": "https://...",
      "sha256": "…",
      "size_bytes": 12345678,
      "etag": "…",
      "last_modified": "…",
      "first_seen": "2026-11-10T00:00:00Z",
      "superseded": false
    }
  ],
  "overlay": {
    "status": "none",
    "url": null,
    "corners": null,
    "source_sha256": null,
    "accuracy_note": null
  },
  "first_seen": "2026-11-10T00:00:00Z",
  "last_changed": "2026-11-10T00:00:00Z",
  "last_checked": "2026-11-15T02:00:00Z",
  "removed_from_source": false
}
```

(The example values are illustrative only — real data must come from scraping.)

**changes.json**

```json
{
  "runs": [
    {
      "run_at": "2026-11-15T02:00:00Z",
      "new": ["surat-tp-90"],
      "changed": [{ "id": "surat-tp-57", "what": ["map_file"] }],
      "removed_from_source": [],
      "failed_sources": ["vadodara-vmc"]
    }
  ]
}
```

**Enums**

- `scheme_type`: `TP` | `DP` | `LAP` | `VILLAGE`
- `status`: `draft` | `preliminary` | `final` | `sanctioned_variation` | `unknown`
- `files[].kind`: `map` | `scheme_book` | `notification` | `redistribution_statement` | `other`
- `overlay.status`: `none` | `done` | `outdated`
- `overlay.corners`: `[[lon,lat] top-left, top-right, bottom-right, bottom-left]`
- `changed[].what`: `map_file` | `other_file` | `status` | `name` | `new_file`

**Rules**

- `id` is deterministic: `{city_id}-{type}-{scheme_no}` (lowercase; slashes and spaces → dashes).
- **Never delete** a scheme. If it disappears from the source site, set `removed_from_source: true` and keep it.
- When a file's sha256 changes, keep the old entry with `superseded: true` and add the new one.
- **Outdated overlay detection:** `overlay.source_sha256` stores the sha256 of the map file the overlay was made from. If the current map file's sha256 differs, set `overlay.status = "outdated"`.
- `schema_version` is an integer. Only increase it for breaking changes. The app ignores a remote catalog whose `schema_version` is higher than it supports and keeps using its current copy.
- Validate all output with pydantic and export a JSON Schema to `docs/catalog-schema.md`.
- Keep files small: no pretty-printing in published JSON; overlay PNGs optimized (target < 2 MB each). GitHub Pages sites have a size limit (about 1 GB), so warn in the run report if the `catalog` branch passes 500 MB.

---

## 6. Python pipeline

**Stack:** Python 3.12, `uv`, `httpx`, `beautifulsoup4`, `playwright` (only if a site truly needs JavaScript), `pydantic` v2, `pypdf`, `pymupdf` (PDF → image), `rasterio`/GDAL (georeferencing), `pillow`/`oxipng` (PNG optimization), `pytest`, `ruff`.

**Scraper interface**

```python
class BaseScraper(ABC):
    city_id: str
    authority: str

    @abstractmethod
    def discover(self) -> list[SchemeRecord]:
        """Return scheme metadata and file URLs found on the source site."""
```

**CLI**

```bash
uv run python -m opennaksha.run                          # all enabled scrapers
uv run python -m opennaksha.run --city surat             # one city
uv run python -m opennaksha.run --previous ./prev        # diff against a previous catalog folder
uv run python -m opennaksha.run --no-download            # metadata only
uv run python -m opennaksha.georef surat-tp-57           # build overlay for one scheme
```

**Run flow**

1. Load the previous catalog (from `--previous`, which in CI is the checked-out `catalog` branch). If none exists, this is the first run.
2. Run each enabled scraper's `discover()`. If a scraper fails, log it in `failed_sources` and **keep that source's previous data unchanged** (never wipe a city because a site was down).
3. For each file: HEAD request first. Download and hash only if the file is new, or ETag / Last-Modified / Content-Length changed, or these headers are missing and the file hasn't been hashed in 30 days.
4. Diff against the previous catalog → set `first_seen`, `last_changed`, `superseded`, `removed_from_source`, `overlay.status = outdated` as per §5.
5. Build overlays for any scheme that has a `.points` file in `pipeline/georef_points/` but no up-to-date overlay.
6. Write `index.json`, city files, and append the run to `changes.json`; validate everything.
7. Print a human-readable run report (also written to the GitHub Actions job summary).

**Scraper etiquette:** clear User-Agent with a contact email from env var `OPENNAKSHA_CONTACT`, 1 req/sec/host, local HTTP cache during development.

---

## 7. Automatic updates (GitHub Actions + Pages)

**`.github/workflows/update-catalog.yml`**

- Triggers: `schedule` (weekly, e.g. Sunday 02:00 IST = Saturday 20:30 UTC) and `workflow_dispatch` (manual "Run workflow" button).
- Steps:
  1. Check out `main` (code) and the `catalog` branch (previous data) into a separate folder.
  2. Set up Python + uv, install dependencies (cache them).
  3. Run `uv run python -m opennaksha.run --previous <catalog-folder>`.
  4. Copy output into the `catalog` folder. If anything changed, commit with message `catalog: <date> — N new, M changed` and push. If nothing changed, don't commit.
  5. Write the run report to the job summary.
  6. If any source failed 3 runs in a row, open (or update) a GitHub issue titled `Source failing: <source>` so the human notices broken scrapers.
- Permissions: `contents: write`, `issues: write`. Uses the built-in `GITHUB_TOKEN` (no personal secrets needed).
- Set `OPENNAKSHA_CONTACT` as a repository variable.
- Add a `concurrency` group so two runs never overlap.

**GitHub Pages:** serve from the `catalog` branch, root folder. Add an empty `.nojekyll` file to the branch.

**Overlay updates:** when the human adds or fixes a `.points` file and pushes to `main`, the workflow should also run (trigger on `push` to paths `pipeline/georef_points/**`) so the new overlay is published right away.

**Known limitation to document in `docs/updates.md`:** GitHub may automatically disable scheduled workflows in public repos after a long period of no repository activity. Explain how to check the Actions tab and re-enable it.

**Bootstrap the first time (document step-by-step in `docs/updates.md`):**

1. Create the GitHub repo and push `main`.
2. Create an empty `catalog` branch (`git switch --orphan catalog`), add `.nojekyll`, push.
3. Repo Settings → Pages → Source: deploy from branch `catalog`, folder `/ (root)`.
4. Repo Settings → Actions → General → Workflow permissions: Read and write.
5. Run the workflow manually once; confirm `https://<user>.github.io/<repo>/catalog/index.json` opens in a browser.
6. Put that base URL into the Android Gradle config.

---

## 8. Android app

**Stack**

- Kotlin, Jetpack Compose, Material 3
- MVVM, Hilt for dependency injection, coroutines + Flow
- `kotlinx.serialization` for catalog JSON
- OkHttp (with HTTP cache) for catalog, overlay and PDF downloads
- Room for the catalog cache, downloads and recently viewed; DataStore for settings
- WorkManager for background downloads and the optional periodic catalog check
- **MapLibre Native Android** for maps
  - Basemap: a free, key-less OpenStreetMap-based style (e.g. OpenFreeMap). Keep the style URL in one config constant.
  - TP overlays: MapLibre `ImageSource` using the overlay PNG (downloaded from GitHub Pages and cached) and its 4 corner coordinates.
- PDF viewing: `android.graphics.pdf.PdfRenderer` with zoom/pan. TP map PDFs are huge — render only the visible region at the needed resolution, never the whole page at full zoom (avoid out-of-memory crashes).
- minSdk 26, targetSdk latest stable
- Package id: `in.opennaksha.app` (change if renamed)

**Module structure**

```
android/
├── app/                 # MainActivity, navigation, DI setup
├── core/model/          # data classes matching the catalog schema
├── core/data/           # catalog repository (remote + Room + bundled), downloads, DataStore
├── core/ui/             # theme, shared composables
├── feature/catalog/     # home, scheme list, search, scheme detail, "what's new"
├── feature/viewer/      # PDF viewer
├── feature/map/         # MapLibre map, overlays, GPS
├── feature/downloads/
└── feature/settings/
```

(A single `app` module with these as packages is acceptable if simpler — record the choice in `docs/decisions.md`.)

**Catalog update logic (core/data)**

1. **First launch:** load the catalog bundled in `assets/` into Room so the app works immediately, even offline.
2. **Every launch** (and on pull-to-refresh, and optionally every 24 h via WorkManager when on Wi-Fi): request `index.json` with `If-None-Match` / `If-Modified-Since`.
   - `304 Not Modified` → do nothing.
   - New `generated_at` → download the changed city files, validate, then replace data in Room inside a single transaction (all or nothing).
   - Network error, invalid JSON, or unsupported `schema_version` → keep current data, log it, show nothing alarming to the user.
3. After an update, compute what's new since the user's last visit (using `first_seen` / `last_changed`) and show a "What's new" badge.
4. Downloaded PDFs: if a scheme's map file sha256 changed, mark the downloaded copy as **"Newer version available"** with an Update button. Don't delete the old copy until the new one downloads successfully.

**Screens**

1. **Home** — city cards, global search bar, recently viewed, "What's new" card (e.g. "3 new schemes in Surat this week"), "Last updated: <date>" line.
2. **Scheme list** — filter by status/type, search by scheme number or area name (English and Gujarati), sort by number or date, "New" and "Updated" badges.
3. **Scheme detail** — name, number, status, date, authority, file list, "Open official source" button, "View on map" (if overlay exists), download, share. Shows "Map updated on <date>" when the file changed, and a notice if the scheme was removed from the source site.
4. **PDF viewer** — smooth zoom/pan, works offline once downloaded, share button.
5. **Map** — basemap, outlines for schemes with overlays, tap to open, overlay opacity slider, "my location" button. Overlays with `status = outdated` show a warning banner: "This scheme's map was updated. This overlay may be outdated — check the latest PDF."
6. **What's new** — list of recent changes from `changes.json`, grouped by date.
7. **Downloads** — offline files, storage used, delete, "Update available" markers.
8. **Settings** — English / ગુજરાતી, check for updates now, auto-check on Wi-Fi only (toggle), clear cache, about, disclaimer, open-source licenses.

**Behaviour**

- Browsing the catalog always works offline.
- Opening a map downloads the PDF from the official URL with a progress indicator, then caches it.
- If a government site is down or slow, show a clear error with "Retry" and "Open in browser".
- Location permission requested only when the user taps "my location".

**Disclaimer** (shown on first launch, must be acknowledged; also in Settings):

> OpenNaksha is an independent app and is not affiliated with or endorsed by any government entity. Maps come from publicly available government websites, linked with each map. Maps are for reference only and are not legal documents. Map overlays are approximate and may be outdated. Always verify with the concerned authority.

**Localization:** `values/strings.xml` (English) and `values-gu/strings.xml` (Gujarati).

**Quality:** unit tests for catalog parsing, update logic (304, new data, bad data, unsupported schema), and diff-related UI states; no crashes with large PDFs on a low-end phone; content descriptions on icons.

---

## 9. Running on your phone

**One-time phone setup**

1. Settings → About phone → tap **Build number** 7 times to enable Developer options.
2. Settings → Developer options → turn on **USB debugging** (and **Wireless debugging** if you want no cable, Android 11+).

**Build and install (USB)**

1. Connect the phone with a USB cable, accept the "Allow USB debugging?" prompt.
2. Check it's detected: `adb devices`
3. Either open `android/` in Android Studio, select your phone, and press **Run ▶**, or from a terminal:

```bash
./scripts/sync_assets.sh          # copies the latest catalog into the app as the offline fallback
cd android && ./gradlew installDebug
```

`sync_assets.sh` downloads the latest published catalog from GitHub Pages if available, otherwise copies from `pipeline/output/` (run the pipeline locally first in that case).

**Wireless (Android 11+)**

Developer options → Wireless debugging → Pair device with pairing code, then:

```bash
adb pair <ip>:<pairing-port>     # enter the code shown on the phone
adb connect <ip>:<port>
cd android && ./gradlew installDebug
```

**After installing:** data updates arrive automatically. Reinstall only when the app's features/code change.

**Sharing with friends (optional):** `./gradlew assembleDebug` → send `android/app/build/outputs/apk/debug/app-debug.apk`; they enable "Install unknown apps" to install it. They'll get automatic data updates too.

---

## 10. How the human keeps things running (document in `docs/updates.md`)

- **Weekly:** nothing — updates run on their own.
- **When an "Source failing" issue appears:** a government site changed its layout. Open Claude Code and say "Fix the scraper for <source> — see the issue." Re-run the workflow manually afterwards.
- **When an overlay is marked outdated:** open the new PDF in QGIS, redo the control points, save over `pipeline/georef_points/{scheme_id}.points`, push. The workflow republishes the overlay automatically.
- **To add a new city/authority:** ask Claude Code to research it (like Milestone 1) and add a scraper.
- **If updates seem stuck:** check the Actions tab on GitHub; re-enable the scheduled workflow if GitHub disabled it.

---

## 11. Milestones

### Milestone 0 — Project setup
- Create the layout from §4, README, `.gitignore`, MIT license.
- Python project with ruff + pytest and one passing test.
- Android project skeleton (Compose, Hilt, MapLibre dependency) that shows a "Hello OpenNaksha" screen.
- `scripts/sync_assets.sh` and `.ps1`.
- `ci.yml` running lint + tests.

**Done when:** `uv run pytest` passes and the skeleton app installs and opens on the human's phone (§9).

### Milestone 1 — Source research (no guessing)
- Visit each target site and record in `docs/sources.md`: TP listing page URLs, page structure, file URL patterns, whether JavaScript is needed, robots.txt notes, whether files send ETag/Last-Modified headers, language, how often it seems to update.
- Targets in order: Surat (SMC, SUDA), Ahmedabad (AMC, AUDA), Vadodara (VMC, VUDA), Rajkot (RMC, RUDA), and `townplanning.gujarat.gov.in`.
- If a site can't be reached or parsed, write that down and move on.

**Done when:** every target has a verdict: scrapable yes / no / partial. Stop and show the human.

### Milestone 2 — Pipeline (Surat first)
- Models, catalog builder, diff logic (§5, §6), CLI.
- Surat scraper end-to-end with HTML fixture tests.
- Tests for diff logic: new scheme, changed file, removed from source, failed source keeps old data, outdated overlay.
- Then add other sites marked "yes", one at a time, each with tests.

**Done when:** `pipeline/output/catalog/` has valid JSON with real Surat schemes (and any other working cities), and running twice with `--previous` shows zero changes the second time.

### Milestone 3 — Android app (catalog + viewer, offline)
- Screens 1, 2, 3, 4, 7, 8 from §8 (no map, no remote updates yet).
- Catalog loaded from bundled assets into Room, PDF download + cache, Gujarati strings, disclaimer on first launch.

**Done when:** on the human's phone, they can find a real Surat scheme, open its map, download it, then view it again in airplane mode.

### Milestone 4 — Automatic updates
- `update-catalog.yml` workflow (§7) with diff, conditional commit, job summary, failing-source issues.
- Write `docs/updates.md` with the bootstrap steps; guide the human through creating the repo, `catalog` branch and Pages.
- App: remote catalog check with ETag, atomic Room update, schema-version check, "What's new" screen (6) and badges, "Newer version available" for downloaded PDFs, "Last updated" line, Settings options.
- Update `sync_assets.sh` to pull the published catalog.

**Done when:**
1. A manual workflow run publishes the catalog and it opens in a browser at the Pages URL.
2. To test the full loop: the human (or Claude Code, using a test entry on a test run) changes the published catalog, opens the app, and sees the change and "What's new" badge **without reinstalling**.
3. The app still works normally in airplane mode.

### Milestone 5 — Georeferencing + map screen
- Write `docs/georeferencing.md`: how to place control points in QGIS Georeferencer against OpenStreetMap and save the `.points` file into `pipeline/georef_points/{scheme_id}.points`.
- `uv run python -m opennaksha.georef {scheme_id}`: render PDF page to a high-res image → warp using control points (EPSG:4326) → export optimized PNG (max ~4096 px on the long side, transparent outside the map) + 4 corner coordinates → set `overlay` fields including `source_sha256`.
- Workflow trigger on `pipeline/georef_points/**` so new overlays publish automatically.
- Map screen (screen 5) with ImageSource overlays, opacity slider, GPS, tap-to-open, outdated-overlay banner.
- The human georeferences 2–3 Surat schemes as a test; Claude Code builds the tooling and helps debug.

**Done when:** standing inside a georeferenced scheme area, the phone's GPS dot appears in roughly the right place on the overlay (labelled "approximate"), and the overlay arrived via automatic update, not a reinstall.

### Milestone 6 — Extras
- Land unit converter: sq m, sq ft, sq yard (vaar), guntha, vigha/bigha (document the Gujarat values used and note they vary by region), acre, hectare.
- DP zoning documents per city where available.
- Links (open in browser only) to official land record portals such as AnyROR — no scraping of these.
- "Report a wrong/outdated map" button that opens a pre-filled email or GitHub issue.
- Optional: a small in-app notice when a new app version is published (check a `latest_app_version` field in `index.json`), linking to the APK download on GitHub Releases.

### Later (not now)
- Plot-level data (tap a final plot to see its number, area, use).
- Village cadastral maps where licensing allows.
- More states, Play Store release, iOS.

---

## 12. Questions to ask the human (only when relevant)

1. Final app name and package id? (Milestone 0)
2. Windows, macOS or Linux computer? (Milestone 0, for scripts)
3. Contact email for the scraper User-Agent? (Milestone 2)
4. GitHub username, repo name, and public or private repo? (Milestone 4)
5. Which schemes to georeference first? (Milestone 5)
