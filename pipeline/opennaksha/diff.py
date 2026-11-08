"""Merge freshly discovered schemes into the previous catalog (PLAN.md §5 rules, §6 step 4).

Rules:
- Never delete a scheme. Missing from a source that was read successfully → removed_from_source.
- Schemes of a source that failed (or wasn't run) are kept exactly as they were.
- A file whose sha256 changed keeps its old entry with ``superseded: true``; a new entry is added.
- A file that disappears from the source is marked superseded.
- An overlay made from a map file that is no longer current becomes ``outdated``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from opennaksha.files import FileState
from opennaksha.models import (
    ChangeWhat,
    DiscoveredScheme,
    FileEntry,
    RunChanges,
    SchemeChange,
    SchemeRecord,
)


@dataclass
class Discovered:
    """One discovered scheme plus the checked state of each of its file URLs."""

    scheme: DiscoveredScheme
    file_states: dict[str, FileState] = field(default_factory=dict)


def _entry(df_kind: str, title: str, url: str, st: FileState, now: datetime) -> FileEntry:
    return FileEntry(
        kind=df_kind,  # type: ignore[arg-type]
        title=title,
        url=url,
        sha256=st.sha256,
        size_bytes=st.size_bytes,
        etag=st.etag,
        last_modified=st.last_modified,
        first_seen=now,
        last_hashed=st.last_hashed,
    )


def _file_change(kind: str) -> ChangeWhat:
    return "map_file" if kind == "map" else "other_file"


def merge_files(
    prev_files: list[FileEntry], found: Discovered, now: datetime, *, is_new: bool
) -> tuple[list[FileEntry], set[ChangeWhat]]:
    what: set[ChangeWhat] = set()
    files = [f.model_copy() for f in prev_files]
    current = {f.url: i for i, f in enumerate(files) if not f.superseded}
    seen: set[str] = set()

    for df in found.scheme.files:
        if df.url in seen:
            continue
        seen.add(df.url)
        st = found.file_states.get(df.url) or FileState()
        idx = current.get(df.url)
        if idx is None:
            files.append(_entry(df.kind, df.title, df.url, st, now))
            if not is_new:
                what.add("new_file")
            continue
        pf = files[idx]
        if pf.sha256 and st.sha256 and pf.sha256 != st.sha256:
            files[idx] = pf.model_copy(update={"superseded": True})
            files.append(_entry(df.kind, df.title, df.url, st, now))
            what.add(_file_change(df.kind))
        else:
            files[idx] = pf.model_copy(
                update={
                    "kind": df.kind,
                    "title": df.title,
                    "sha256": st.sha256 or pf.sha256,
                    "size_bytes": st.size_bytes if st.size_bytes is not None else pf.size_bytes,
                    "etag": st.etag if st.etag is not None else pf.etag,
                    "last_modified": st.last_modified or pf.last_modified,
                    "last_hashed": st.last_hashed or pf.last_hashed,
                }
            )

    for url, idx in current.items():
        if url not in seen:
            files[idx] = files[idx].model_copy(update={"superseded": True})
            what.add(_file_change(files[idx].kind))
    return files, what


def _overlay_outdated(record: SchemeRecord) -> bool:
    ov = record.overlay
    if ov.status != "done" or not ov.source_sha256:
        return False
    current = {f.sha256 for f in record.current_files() if f.kind == "map" and f.sha256}
    return bool(current) and ov.source_sha256 not in current


def merge_scheme(
    prev: SchemeRecord | None, found: Discovered, now: datetime
) -> tuple[SchemeRecord, set[ChangeWhat] | None]:
    """Returns the merged record and the set of changes (None means a brand-new scheme)."""
    d = found.scheme
    files, what = merge_files(prev.files if prev else [], found, now, is_new=prev is None)

    if prev is None:
        record = SchemeRecord(
            id=d.id,
            city_id=d.city_id,
            authority=d.authority,
            scheme_type=d.scheme_type,
            scheme_no=d.scheme_no,
            name_en=d.name_en,
            name_gu=d.name_gu,
            status=d.status,
            status_date=d.status_date,
            source_page_url=d.source_page_url,
            files=files,
            first_seen=now,
            last_changed=now,
            last_checked=now,
        )
        return record, None

    if (d.name_en, d.name_gu) != (prev.name_en, prev.name_gu):
        what.add("name")
    if (d.status, d.status_date) != (prev.status, prev.status_date):
        what.add("status")
    if prev.removed_from_source:
        # Back on the source site: treated as a status change so the app shows it.
        what.add("status")

    record = prev.model_copy(
        update={
            "authority": d.authority,
            "name_en": d.name_en,
            "name_gu": d.name_gu,
            "status": d.status,
            "status_date": d.status_date,
            "source_page_url": d.source_page_url,
            "files": files,
            "removed_from_source": False,
            "last_checked": now,
            "last_changed": now if what else prev.last_changed,
        }
    )
    if _overlay_outdated(record):
        record.overlay = record.overlay.model_copy(update={"status": "outdated"})
    return record, what


def merge(
    previous: dict[str, SchemeRecord],
    discovered: list[Discovered],
    succeeded_sources: set[str],
    failed_sources: list[str],
    now: datetime,
) -> tuple[dict[str, SchemeRecord], RunChanges]:
    changes = RunChanges(run_at=now, failed_sources=sorted(failed_sources))
    result: dict[str, SchemeRecord] = {}

    # Merge duplicates (the same scheme listed twice on a site): first listing wins metadata,
    # file lists are combined.
    by_id: dict[str, Discovered] = {}
    for item in discovered:
        sid = item.scheme.id
        if sid in by_id:
            existing = by_id[sid]
            urls = {f.url for f in existing.scheme.files}
            extra = [f for f in item.scheme.files if f.url not in urls]
            existing.scheme = existing.scheme.model_copy(
                update={"files": existing.scheme.files + extra}
            )
            existing.file_states.update(
                {k: v for k, v in item.file_states.items() if k not in existing.file_states}
            )
        else:
            by_id[sid] = Discovered(item.scheme, dict(item.file_states))

    for sid, item in by_id.items():
        record, what = merge_scheme(previous.get(sid), item, now)
        result[sid] = record
        if what is None:
            changes.new.append(sid)
        elif what:
            changes.changed.append(SchemeChange(id=sid, what=sorted(what)))

    for sid, prev in previous.items():
        if sid in result:
            continue
        if prev.source_id in succeeded_sources:
            if not prev.removed_from_source:
                changes.removed_from_source.append(sid)
                prev = prev.model_copy(
                    update={"removed_from_source": True, "last_changed": now, "last_checked": now}
                )
            else:
                prev = prev.model_copy(update={"last_checked": now})
        result[sid] = prev  # failed / not-run sources: unchanged

    changes.new.sort()
    changes.changed.sort(key=lambda c: c.id)
    changes.removed_from_source.sort()
    return result, changes
