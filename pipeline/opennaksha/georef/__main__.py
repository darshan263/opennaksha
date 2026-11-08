"""``uv run python -m opennaksha.georef <scheme_id>`` — build the overlay for one scheme.

  --render-only   write georef_work/<scheme_id>.png (full resolution) to load into QGIS
                  for placing control points (see docs/georeferencing.md)

Without --render-only, reads georef_points/<scheme_id>.points, builds
<catalog>/overlays/<scheme_id>.png and updates the scheme's overlay fields in <catalog>.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from opennaksha.catalog import load_previous, write_catalog
from opennaksha.georef.overlay import (
    RENDER_DPI,
    GeorefError,
    GeorefOptions,
    build_overlay,
    render_pdf_page,
    safe_name,
)
from opennaksha.http import PoliteClient
from opennaksha.run import PIPELINE_DIR, fetch_map_pdf, utcnow


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="opennaksha.georef", description=__doc__)
    p.add_argument("scheme_id")
    p.add_argument("--catalog", type=Path, default=Path("output"), help="catalog folder")
    p.add_argument("--points-dir", type=Path, default=PIPELINE_DIR / "georef_points")
    p.add_argument("--render-only", action="store_true")
    p.add_argument("--page", type=int, help="PDF page (default: sidecar json or 0)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sid = safe_name(args.scheme_id)
    cat = load_previous(args.catalog)
    record = cat.schemes.get(sid)
    if record is None:
        print(f"scheme {sid!r} not found in {args.catalog}/catalog", file=sys.stderr)
        return 2
    points = args.points_dir / f"{sid}.points"
    opts = GeorefOptions.load(points)
    page = args.page if args.page is not None else opts.page

    with PoliteClient() as client:
        pdf = fetch_map_pdf(client, record, opts.file_url, PIPELINE_DIR / ".cache" / "pdf")

    if args.render_only:
        out = PIPELINE_DIR / "georef_work" / f"{sid}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        render_pdf_page(pdf, page).save(out)
        print(f"wrote {out} ({RENDER_DPI} dpi). Load it in QGIS Georeferencer.")
        return 0

    if not points.exists():
        print(f"missing {points}", file=sys.stderr)
        return 2
    try:
        record.overlay = build_overlay(sid, pdf, points, args.catalog / "overlays", page=page)
    except GeorefError as e:
        print(f"georef failed: {e}", file=sys.stderr)
        return 1
    now = utcnow()
    record.last_changed = now
    write_catalog(args.catalog, cat.schemes, cat.changes, cat.status, now)
    print(f"overlay written: {args.catalog / record.overlay.url}")
    print(f"corners: {record.overlay.corners}")
    print(record.overlay.accuracy_note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
