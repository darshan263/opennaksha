"""Decide when a file must be (re)downloaded and hashed (PLAN.md §6 step 3)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from opennaksha.http import HeadInfo, PoliteClient

log = logging.getLogger(__name__)

REHASH_AFTER = timedelta(days=30)


@dataclass
class FileState:
    """Hash and HTTP validators for one file URL."""

    sha256: str | None = None
    size_bytes: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    last_hashed: datetime | None = None


def needs_download(prev: FileState | None, head: HeadInfo | None, now: datetime) -> bool:
    if prev is None or prev.sha256 is None:
        return True
    stale = prev.last_hashed is None or now - prev.last_hashed >= REHASH_AFTER
    if head is None or not head.has_validators:
        return stale  # no validators: only re-hash if it's been a while
    # Compare all validators together: some servers (IIS) derive ETags from timestamps only.
    same = (
        (head.etag is None or head.etag == prev.etag)
        and (head.last_modified is None or head.last_modified == prev.last_modified)
        and (head.content_length is None or head.content_length == prev.size_bytes)
    )
    if not same:
        return True
    # Content-Length alone is weak (an edited file can keep its size): treat like no validators.
    strong = head.etag is not None or head.last_modified is not None
    return not strong and stale


def check_file(
    client: PoliteClient,
    url: str,
    prev: FileState | None,
    now: datetime,
    *,
    no_download: bool = False,
) -> FileState:
    """HEAD the file and download+hash it only when it is new or looks changed."""
    head = client.head(url)
    if not needs_download(prev, head, now) or no_download:
        base = prev or FileState()
        if head is None:
            return base
        return FileState(
            sha256=base.sha256,
            size_bytes=base.size_bytes if base.sha256 else head.content_length,
            etag=head.etag,
            last_modified=head.last_modified,
            last_hashed=base.last_hashed,
        )
    log.info("downloading %s", url)
    dl = client.download(url)
    return FileState(
        sha256=dl.sha256,
        size_bytes=dl.size_bytes,
        etag=head.etag if head else None,
        last_modified=head.last_modified if head else None,
        last_hashed=now,
    )
