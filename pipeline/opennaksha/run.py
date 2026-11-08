"""CLI entry point: ``uv run python -m opennaksha.run`` (PLAN.md §6 run flow).

Outputs (under ``--output``, default ``output/``):
  catalog/index.json, catalog/cities/*.json, catalog/changes.json, catalog/status.json
  overlays/{scheme_id}.png   (only overlays built in this run)
  report.md, report.json     (run report; not published)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from opennaksha import __version__
from opennaksha.catalog import append_run, folder_size, load_previous, write_catalog
from opennaksha.diff import Discovered, merge
from opennaksha.files import FileState, check_file
from opennaksha.georef.overlay import GeorefOptions, build_overlay, sha256_file
from opennaksha.http import PoliteClient
from opennaksha.models import SchemeRecord, SourceHealth
from opennaksha.scrapers import all_scrapers
from opennaksha.scrapers.base import BaseScraper, ScraperError

log = logging.getLogger("opennaksha")

PIPELINE_DIR = Path(__file__).resolve().parent.parent
FAILING_THRESHOLD = 3
SIZE_WARNING_BYTES = 500 * 1024 * 1024


@dataclass
class RunReport:
    run_at: str
    new: list[str] = field(default_factory=list)
    changed: list[dict] = field(default_factory=list)
    removed_from_source: list[str] = field(default_factory=list)
    failed_sources: dict[str, str] = field(default_factory=dict)
    succeeded_sources: list[str] = field(default_factory=list)
    failing_sources: dict[str, int] = field(default_factory=dict)  # >= threshold, for issues
    recovered_sources: list[str] = field(default_factory=list)
    overlays_built: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scheme_count: int = 0
    first_run: bool = False
    should_commit: bool = False
    commit_message: str = ""
    catalog_size_bytes: int = 0


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="opennaksha.run", description="Scrape and build the catalog.")
    p.add_argument("--city", help="run only the scrapers for this city id (e.g. surat)")
    p.add_argument("--previous", type=Path, help="folder holding the previous catalog to diff with")
    p.add_argument("--output", type=Path, default=Path("output"), help="output folder")
    p.add_argument("--no-download", action="store_true", help="metadata only, skip file hashing")
    p.add_argument(
        "--points-dir",
        type=Path,
        default=PIPELINE_DIR / "georef_points",
        help="folder with QGIS .points files",
    )
    p.add_argument("--no-overlays", action="store_true", help="skip building overlays")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def _prev_state(prev: SchemeRecord | None, url: str) -> FileState | None:
    if prev is None:
        return None
    for f in prev.current_files():
        if f.url == url:
            return FileState(f.sha256, f.size_bytes, f.etag, f.last_modified, f.last_hashed)
    return None


def scrape_source(
    scraper: BaseScraper,
    previous: dict[str, SchemeRecord],
    now: datetime,
    *,
    no_download: bool,
    warnings: list[str],
) -> list[Discovered]:
    found = scraper.discover()
    if not found:
        raise ScraperError("no schemes found (layout changed?)")
    items = []
    for d in found:
        prev = previous.get(d.id)
        states: dict[str, FileState] = {}
        for f in d.files:
            if f.url in states:
                continue
            ps = _prev_state(prev, f.url)
            try:
                states[f.url] = check_file(scraper.client, f.url, ps, now, no_download=no_download)
            except Exception as e:  # one broken file must not fail the whole source
                warnings.append(f"{d.id}: could not check {f.url}: {e}")
                states[f.url] = ps or FileState()
        items.append(Discovered(d, states))
    return items


def build_overlays(
    client: PoliteClient,
    schemes: dict[str, SchemeRecord],
    points_dir: Path,
    overlays_dir: Path,
    cache_dir: Path,
    now: datetime,
    warnings: list[str],
) -> list[str]:
    built = []
    if not points_dir.exists():
        return built
    for points in sorted(points_dir.glob("*.points")):
        sid = points.stem
        record = schemes.get(sid)
        if record is None:
            warnings.append(f"{points.name}: no scheme with id {sid!r} in the catalog")
            continue
        if record.overlay.status != "none" and record.overlay.points_sha256 == sha256_file(points):
            continue  # up to date (or outdated with unchanged points: needs new points)
        opts = GeorefOptions.load(points)
        try:
            pdf = fetch_map_pdf(client, record, opts.file_url, cache_dir)
            record.overlay = build_overlay(sid, pdf, points, overlays_dir, page=opts.page)
            record.last_changed = now
            built.append(sid)
        except Exception as e:
            warnings.append(f"overlay {sid} failed: {e}")
    return built


def fetch_map_pdf(
    client: PoliteClient, record: SchemeRecord, file_url: str | None, cache_dir: Path
) -> Path:
    current = record.current_files()
    candidates = [f for f in current if f.url == file_url] if file_url else []
    candidates = candidates or [f for f in current if f.kind == "map"] or current
    if not candidates:
        raise ValueError("scheme has no files")
    f = candidates[0]
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{record.id}-{(f.sha256 or 'latest')[:12]}.pdf"
    if not dest.exists() or f.sha256 is None:
        client.download(f.url, dest)
    return dest


def run(
    args: argparse.Namespace,
    scrapers: list[type[BaseScraper]] | None = None,
    client: PoliteClient | None = None,
) -> RunReport:
    """Run the pipeline. `scrapers` and `client` can be injected by tests."""
    now = utcnow()
    prev = load_previous(args.previous)
    report = RunReport(run_at=now.isoformat().replace("+00:00", "Z"), first_run=prev.is_first_run)

    classes = [c for c in (scrapers if scrapers is not None else all_scrapers()) if c.enabled]
    if args.city:
        classes = [c for c in classes if c.city_id == args.city]
        if not classes:
            report.warnings.append(f"no enabled scrapers for city {args.city!r}")
    insecure = frozenset().union(*(c.insecure_hosts for c in classes)) if classes else frozenset()

    discovered: list[Discovered] = []
    succeeded: set[str] = set()
    own_client = client is None
    if client is None:
        client = PoliteClient(insecure_hosts=insecure)
    try:

        def scrape(cls: type[BaseScraper]) -> list[Discovered]:
            log.info("scraping %s", cls.source_id())
            return scrape_source(
                cls(client),
                prev.schemes,
                now,
                no_download=args.no_download,
                warnings=report.warnings,
            )

        # Sources run in parallel (different hosts); each host is still limited to 1 req/s.
        with ThreadPoolExecutor(max_workers=max(1, min(8, len(classes)))) as pool:
            futures = [(cls.source_id(), pool.submit(scrape, cls)) for cls in classes]
            for sid, fut in futures:  # collected in registry order → deterministic output
                try:
                    items = fut.result()
                    discovered.extend(items)
                    succeeded.add(sid)
                    log.info("%s: %d schemes", sid, len(items))
                except Exception as e:
                    log.error("%s failed: %s", sid, e, exc_info=True)
                    report.failed_sources[sid] = f"{type(e).__name__}: {e}"[:500]

        schemes, run_changes = merge(
            prev.schemes, discovered, succeeded, list(report.failed_sources), now
        )
        if not args.no_overlays:
            report.overlays_built = build_overlays(
                client,
                schemes,
                args.points_dir,
                args.output / "overlays",
                PIPELINE_DIR / ".cache" / "pdf",
                now,
                report.warnings,
            )
    finally:
        if own_client:
            client.close()

    # Source health (for "Source failing" issues).
    status = prev.status.model_copy(deep=True)
    health_changed = False
    for sid, err in report.failed_sources.items():
        h = status.sources.setdefault(sid, SourceHealth())
        h.consecutive_failures += 1
        h.last_error = err
        health_changed = True
    for sid in sorted(succeeded):
        h = status.sources.setdefault(sid, SourceHealth())
        if h.consecutive_failures:
            report.recovered_sources.append(sid)
            health_changed = True
        h.consecutive_failures = 0
        h.last_error = None
        h.last_success = now
    report.failing_sources = {
        sid: h.consecutive_failures
        for sid, h in status.sources.items()
        if h.consecutive_failures >= FAILING_THRESHOLD
    }

    changes = append_run(prev.changes, run_changes)
    write_catalog(args.output, schemes, changes, status, now)

    report.new = run_changes.new
    report.changed = [c.model_dump() for c in run_changes.changed]
    report.removed_from_source = run_changes.removed_from_source
    report.succeeded_sources = sorted(succeeded)
    report.scheme_count = len(schemes)
    report.should_commit = (
        prev.is_first_run
        or run_changes.has_data_changes
        or health_changed
        or bool(report.overlays_built)
    )
    report.commit_message = (
        f"catalog: {now.date().isoformat()} — {len(report.new)} new, {len(report.changed)} changed"
    )
    size = folder_size(args.output / "catalog") + folder_size(args.output / "overlays")
    if args.previous:
        size += folder_size(args.previous / "overlays")  # overlays accumulate on the branch
    report.catalog_size_bytes = size
    if size > SIZE_WARNING_BYTES:
        report.warnings.append(
            f"published data is {size / 1e6:.0f} MB (GitHub Pages limit is about 1 GB)"
        )
    return report


def render_report(r: RunReport) -> str:
    lines = [f"## OpenNaksha catalog run — {r.run_at}", ""]
    if r.first_run:
        lines.append("_First run (no previous catalog)._\n")
    lines += [
        "| | |",
        "|---|---|",
        f"| Schemes in catalog | {r.scheme_count} |",
        f"| New | {len(r.new)} |",
        f"| Changed | {len(r.changed)} |",
        f"| Removed from source | {len(r.removed_from_source)} |",
        f"| Overlays built | {len(r.overlays_built)} |",
        f"| Sources OK | {', '.join(r.succeeded_sources) or '—'} |",
        f"| Sources failed | {', '.join(r.failed_sources) or '—'} |",
        f"| Published size | {r.catalog_size_bytes / 1e6:.1f} MB |",
        f"| Will commit | {'yes' if r.should_commit else 'no (nothing changed)'} |",
        "",
    ]
    if r.new:
        lines += ["### New", *[f"- `{s}`" for s in r.new], ""]
    if r.changed:
        lines += ["### Changed", *[f"- `{c['id']}`: {', '.join(c['what'])}" for c in r.changed]]
        lines.append("")
    if r.removed_from_source:
        lines += ["### Removed from source", *[f"- `{s}`" for s in r.removed_from_source], ""]
    if r.failed_sources:
        lines += ["### Failed sources", *[f"- `{k}`: {v}" for k, v in r.failed_sources.items()]]
        lines.append("")
    if r.failing_sources:
        lines += [
            f"### Failing {FAILING_THRESHOLD}+ runs in a row",
            *[f"- `{k}`: {n} runs" for k, n in r.failing_sources.items()],
            "",
        ]
    if r.warnings:
        lines += ["### Warnings", *[f"- {w}" for w in r.warnings], ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    report = run(args)
    md = render_report(report)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.md").write_text(md, encoding="utf-8")
    (args.output / "report.json").write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    print(md)
    # Exit 0 even when sources fail: the catalog is still valid and failures are reported.
    return 0


if __name__ == "__main__":
    sys.exit(main())
