#!/usr/bin/env bash
# Copies the latest catalog into the Android app's assets (the offline fallback bundled in the APK).
#
# 1. If a catalog base URL is configured, download index.json, changes.json and every city file.
# 2. Otherwise (or if the download fails) copy from pipeline/output/catalog/.
# 3. If neither is available, keep whatever is already in the assets folder.
#
# The base URL comes from $OPENNAKSHA_CATALOG_URL, or else `opennaksha.catalogBaseUrl` in
# android/gradle.properties (e.g. https://<user>.github.io/<repo>).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/android/app/src/main/assets/catalog"
LOCAL="$ROOT/pipeline/output/catalog"

base="${OPENNAKSHA_CATALOG_URL:-}"
if [[ -z "$base" && -f "$ROOT/android/gradle.properties" ]]; then
  base="$(grep -E '^opennaksha\.catalogBaseUrl=' "$ROOT/android/gradle.properties" | cut -d= -f2- | tr -d '\r' || true)"
fi
base="${base%/}"

download() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  mkdir -p "$tmp/cities"
  echo "Downloading catalog from $base/catalog/ ..."
  curl -fsSL --max-time 60 -o "$tmp/index.json" "$base/catalog/index.json" || return 1
  curl -fsSL --max-time 60 -o "$tmp/changes.json" "$base/catalog/changes.json" || true
  # index.json lists only city objects, so every "id" in it is a city id.
  local ids
  ids="$(grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]+"' "$tmp/index.json" | sed -E 's/.*"([^"]+)"$/\1/')"
  for id in $ids; do
    curl -fsSL --max-time 120 -o "$tmp/cities/$id.json" "$base/catalog/cities/$id.json" || return 1
  done
  rm -rf "$DEST"
  mkdir -p "$DEST"
  cp -R "$tmp/." "$DEST/"
}

if [[ -n "$base" ]] && download; then
  echo "Bundled catalog updated from $base"
elif [[ -f "$LOCAL/index.json" ]]; then
  echo "Copying local pipeline output from $LOCAL"
  rm -rf "$DEST"
  mkdir -p "$DEST"
  cp -R "$LOCAL/." "$DEST/"
else
  echo "No published catalog and no pipeline/output/catalog found; keeping existing assets." >&2
  echo "Run the pipeline first:  cd pipeline && uv run python -m opennaksha.run" >&2
fi
