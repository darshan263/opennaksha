# OpenNaksha

A free, no-login Android app for viewing Town Planning (TP) scheme maps, Development Plans (DP)
and village maps published by government authorities in Gujarat, India.

- Catalog data is scraped weekly by GitHub Actions and published on GitHub Pages. No server, no paid services.
- Map PDFs are always downloaded directly from the official government URLs.
- Every scheme links back to its official source.

> OpenNaksha is an independent app and is not affiliated with or endorsed by any government entity.
> Maps are for reference only and are not legal documents. Always verify with the concerned authority.

See [`PLAN.md`](PLAN.md) for the full build plan and milestones.

## Repository layout

| Path | What |
|---|---|
| `pipeline/` | Python scraper + catalog builder (`uv`, Python 3.12) |
| `android/` | Android app (Kotlin, Jetpack Compose, Hilt, MapLibre) |
| `scripts/` | Helper scripts (`sync_assets.sh` / `.ps1`) |
| `docs/` | Source research, schema, update and georeferencing docs, decision log |
| `.github/workflows/` | CI and the weekly catalog update |

## Prerequisites

- Android Studio (latest stable), which includes the Android SDK, `adb` and a JDK 17+
- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Git

## Pipeline

```bash
cd pipeline
uv sync
uv run ruff check .
uv run pytest
```

## Android app

Open `android/` in Android Studio and press **Run**, or from a terminal:

```bash
./scripts/sync_assets.sh        # Windows: .\scripts\sync_assets.ps1
cd android
./gradlew installDebug          # Windows: .\gradlew.bat installDebug
```

See PLAN.md §9 for phone setup (USB / wireless debugging).

## License

MIT, see [LICENSE](LICENSE).
