# Automatic updates

The catalog updates itself every week. No server and no PC need to be on.

```
GitHub Actions (weekly) → pipeline scrapes official sites → diff with previous catalog
  → commit to the `catalog` branch → GitHub Pages serves it → the app checks it on launch
```

- **Workflow:** `.github/workflows/update-catalog.yml`
  - Runs every Sunday at 02:00 IST (Saturday 20:30 UTC).
  - Runs on demand with **Actions → Update catalog → Run workflow**.
  - Runs whenever a file under `pipeline/georef_points/` is pushed to `main`.
- **Previous data:** the workflow checks out the `catalog` branch and passes it to the pipeline
  as `--previous`. If a site is down, that site's schemes are kept unchanged.
- **Commit rule:** the workflow commits only when something real changed. That means a new,
  changed or removed scheme, a new overlay, or a change in which sources are failing. Otherwise
  it commits nothing.
- **Run report:** it appears on the workflow run page (job summary). It lists new, changed and
  removed schemes, failed sources and warnings.
- **Broken scrapers:** when a source fails 3 runs in a row, an issue titled
  `Source failing: <source>` is opened, or commented on if it is already open. It closes itself
  when the source works again.
- **History:** the git history of the `catalog` branch is a permanent record of every change to
  every scheme.

Published URLs (replace `<user>` and `<repo>`):

```
https://<user>.github.io/<repo>/catalog/index.json
https://<user>.github.io/<repo>/catalog/cities/{city_id}.json
https://<user>.github.io/<repo>/catalog/changes.json
https://<user>.github.io/<repo>/overlays/{scheme_id}.png
```

## The app side

- **First launch:** the app loads the catalog bundled in the APK, so it works offline straight away.
- **Every launch, pull-to-refresh, or "Check for updates now" in Settings:** the app requests
  `index.json` with `If-None-Match` / `If-Modified-Since`.
  - `304` means nothing to do.
  - A new `generated_at` means the city files are downloaded, validated and swapped in all at
    once (all or nothing).
- **Optional auto-check:** about every 24 hours in the background (Wi-Fi only by default; see
  Settings).
- **Errors:** an error, invalid JSON, or a higher `schema_version` than the app supports keeps
  the current data silently.

## One-time bootstrap

You need a free GitHub account. A **public** repository is recommended: Actions minutes are free
and Pages works on the free plan.

1. **Create the repo** on github.com (e.g. `opennaksha`), empty, without a README. Then from the
   project folder:
   ```bash
   git remote add origin https://github.com/<user>/<repo>.git
   git push -u origin main
   ```
2. **Create the empty `catalog` branch:**
   ```bash
   git switch --orphan catalog
   git commit --allow-empty -m "catalog: init"
   touch .nojekyll && git add .nojekyll && git commit -m "catalog: add .nojekyll"
   git push -u origin catalog
   git switch main
   ```
   If `git switch main` complains about untracked files, they are build outputs (e.g.
   `pipeline/output`) and are safe to leave.
3. **Turn on Pages:** Repo **Settings → Pages → Build and deployment → Source: Deploy from a
   branch**, branch `catalog`, folder `/ (root)`, Save.
4. **Allow the workflow to push:** **Settings → Actions → General → Workflow permissions → Read
   and write permissions**, Save.
5. **Set the scraper contact:** **Settings → Secrets and variables → Actions → Variables → New
   repository variable**: `OPENNAKSHA_CONTACT` = an email or URL that government site admins can
   use to reach you. It is sent in the User-Agent header.
6. **Run it once:** **Actions → Update catalog → Run workflow**. When it is green, open
   `https://<user>.github.io/<repo>/catalog/index.json` in a browser. The first Pages deploy
   can take a few minutes.
7. **Point the app at it:** in `android/gradle.properties` set
   `opennaksha.catalogBaseUrl=https://<user>.github.io/<repo>`. Then run
   `./scripts/sync_assets.sh` (Windows: `.\scripts\sync_assets.ps1`) so the APK bundles the
   latest catalog, and rebuild/install the app.

## Keeping things running

- **Weekly:** nothing to do. Updates run on their own.
- **When a `Source failing: …` issue appears:** a government site changed its layout. Open
  Claude Code in this folder and say *"Fix the scraper for `<source>` — see the issue."* Push the
  fix, then re-run the workflow manually.
- **When an overlay is marked outdated:** the app shows a warning on that scheme's map. Open the
  new PDF in QGIS, redo the control points, save over
  `pipeline/georef_points/{scheme_id}.points` and push. The workflow republishes the overlay.
  See [georeferencing.md](georeferencing.md).
- **To add a new city or authority:** ask Claude Code to research it (like Milestone 1, see
  [sources.md](sources.md)) and add a scraper.
- **If updates seem stuck:** check the **Actions** tab (see below).

## Troubleshooting

**Scheduled runs stopped.** GitHub automatically disables scheduled workflows in public
repositories after **60 days without repository activity**, and the bot's commits to the
`catalog` branch may not count. Open **Actions → Update catalog**. If you see a banner like "This
scheduled workflow is disabled because there hasn't been activity in this repository for at
least 60 days", click **Enable workflow**. Any push to `main` also counts as activity.

**The workflow fails at "Check out previous catalog".** The `catalog` branch doesn't exist yet.
Do bootstrap step 2.

**The workflow fails at "Publish" with a 403.** Workflow permissions are read-only. Do bootstrap
step 4.

**The Pages URL gives 404.** Check **Settings → Pages**: the source must be the `catalog` branch,
`/ (root)`. Wait a few minutes after the first commit, and check the "pages build and deployment"
run in the Actions tab.

**The app doesn't show new data.**
- Check that `opennaksha.catalogBaseUrl` in `android/gradle.properties` is set and the app was
  rebuilt after setting it.
- Use **Settings → Check for updates now** in the app.
- Open the `index.json` URL in the phone's browser to confirm it is reachable.

**Size.** GitHub Pages sites are limited to about 1 GB. The run report warns when published data
passes 500 MB. Overlay PNGs are the main cost (target < 2 MB each).

## Running the pipeline locally

```bash
cd pipeline
uv sync
uv run python -m opennaksha.run                       # all enabled scrapers → output/
uv run python -m opennaksha.run --city surat --no-download
uv run python -m opennaksha.run --previous ./output   # diff against a previous run
```

Set `OPENNAKSHA_HTTP_CACHE=1` to cache fetched HTML pages in `pipeline/.http_cache/` while
developing a scraper.
