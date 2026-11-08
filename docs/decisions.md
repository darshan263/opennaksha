# Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-08 | Keep the working name **OpenNaksha** and package id `in.opennaksha.app` for now. | PLAN.md §12 Q1 is still open. The name is easy to change before the first release. |
| 2026-11-08 | Use a **single `app` module** with feature packages (`core.*`, `feature.*`) instead of multiple Gradle modules. | PLAN.md §8 allows it. Fewer build files and faster builds for a one-person project. We can split into modules later if build times grow. |
| 2026-11-08 | Pin **AGP 8.13.2 / Gradle 8.14.3 / Kotlin 2.2.21 / KSP 2.2.21-2.0.5 / Hilt 2.57.2**, compileSdk/targetSdk 36. | This is a known-compatible set. AGP 9.x changes how Kotlin is configured. Upgrade later with Android Studio's AGP Upgrade Assistant, once the app builds. |
| 2026-11-08 | Use **MapLibre Android 12.3.1** (latest 12.x) and no 13.x / globe builds yet. | It is a stable line with the `ImageSource` + `LatLngQuad` API we need for overlays. It needs no API key. |
| 2026-11-08 | Use **OpenFreeMap "liberty"** (`https://tiles.openfreemap.org/styles/liberty`) as the default basemap style. | It is free, needs no key, and is based on OpenStreetMap (PLAN.md §8). It is kept in one constant, `MapConfig.STYLE_URL`. |
| 2026-11-08 | Use **hatchling** as the pipeline build backend, with the package at `pipeline/opennaksha/`. | It is simple and standard with uv, and gives the `python -m opennaksha.run` layout from PLAN.md §6. |
| 2026-11-08 | applicationId stays `in.opennaksha.app`, but the Kotlin package / Gradle `namespace` is **`app.opennaksha`**. | `in` is a reserved word in Kotlin, so `package in.opennaksha.app` would need backticks in every file. The applicationId (what Android and installs see) is unchanged. |
| 2026-11-08 | Ship an **empty bundled catalog** (`assets/catalog/index.json`, no cities, `generated_at` 1970) until Milestone 2 produces real data. | The app needs something to load on first launch. An empty list is not invented data (PLAN.md §2). |
| 2026-11-08 | Launcher icon is a plain vector map pin (adaptive icon only, minSdk 26). | It is a placeholder until the app name is final. |
