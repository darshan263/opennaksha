#!/usr/bin/env bash
# Scrape sources that block GitHub's runners (default: ahmedabad-amc) from this PC and publish
# the result to the `catalog` branch. Other sources' data is left exactly as published.
#
#   ./scripts/publish_local.sh                     # AMC, downloads + hashes new/changed files
#   ./scripts/publish_local.sh ahmedabad-amc --no-download
#
# Needs: git (with push access to the repo) and uv. Run it now and then (e.g. monthly).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCES=()
EXTRA=()
for a in "$@"; do
  case "$a" in
    --*) EXTRA+=("$a") ;;
    *) SOURCES+=("$a") ;;
  esac
done
[[ ${#SOURCES[@]} -eq 0 ]] && SOURCES=(ahmedabad-amc)

WORK="$(mktemp -d)"
cleanup() {
  git -C "$ROOT" worktree remove --force "$WORK/catalog" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "Fetching the published catalog..."
git -C "$ROOT" fetch -q origin catalog
git -C "$ROOT" worktree add -q --detach "$WORK/catalog" origin/catalog

ARGS=(--previous "$WORK/catalog" --output "$WORK/out" --no-overlays)
for s in "${SOURCES[@]}"; do ARGS+=(--source "$s"); done
ARGS+=("${EXTRA[@]}")

cd "$ROOT/pipeline"
uv sync -q --no-dev
if uv run python -c "pass" >/dev/null 2>&1; then
  uv run python -m opennaksha.run "${ARGS[@]}"
else
  # Windows Smart App Control can block uv's venv launcher; use the base interpreter instead.
  PY="$(uv python find 3.12)"
  SEP=":"; [[ "$OSTYPE" == msys* || "$OSTYPE" == cygwin* ]] && SEP=";"
  PYTHONPATH="$(pwd)/.venv/Lib/site-packages${SEP}$(pwd)/.venv/lib/python3.12/site-packages${SEP}$(pwd)" \
    "$PY" -m opennaksha.run "${ARGS[@]}"
fi

REPORT="$WORK/out/report.json"
if ! grep -q '"should_commit": true' "$REPORT"; then
  echo "Nothing changed for ${SOURCES[*]}; nothing to publish."
  exit 0
fi
if grep -q '"failed_sources": {}' "$REPORT"; then :; else
  echo "A source failed (see the report above); not publishing." >&2
  exit 1
fi

rm -rf "$WORK/catalog/catalog"
cp -R "$WORK/out/catalog" "$WORK/catalog/catalog"
touch "$WORK/catalog/.nojekyll"
MSG="$(sed -n 's/.*"commit_message": "\(.*\)",*/\1/p' "$REPORT") (local: ${SOURCES[*]})"
cd "$WORK/catalog"
git add -A
git commit -q -m "$MSG"
git push -q origin HEAD:catalog
echo "Published: $MSG"
echo "GitHub Pages updates in a minute or two; the app picks it up on its next check."
