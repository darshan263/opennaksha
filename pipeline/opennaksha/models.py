"""Pydantic models for the published catalog (PLAN.md §5) and for scraper output.

The published JSON is the contract with the Android app. Adding optional fields is fine;
anything else that would break an old app must bump ``SCHEMA_VERSION``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

SchemeType = Literal["TP", "DP", "LAP", "VILLAGE"]
Status = Literal["draft", "preliminary", "final", "sanctioned_variation", "unknown"]
FileKind = Literal["map", "scheme_book", "notification", "redistribution_statement", "other"]
OverlayStatus = Literal["none", "done", "outdated"]
ChangeWhat = Literal["map_file", "other_file", "status", "name", "new_file"]

LonLat = tuple[float, float]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- published


class FileEntry(_Model):
    kind: FileKind
    title: str
    url: str
    sha256: str | None = None
    size_bytes: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    first_seen: datetime
    superseded: bool = False
    # When the file was last downloaded and hashed (drives the 30-day re-hash rule, §6 step 3).
    last_hashed: datetime | None = None


class Overlay(_Model):
    status: OverlayStatus = "none"
    # Relative to the catalog base URL, e.g. "overlays/surat-tp-57.png".
    url: str | None = None
    # [[lon, lat] top-left, top-right, bottom-right, bottom-left]
    corners: tuple[LonLat, LonLat, LonLat, LonLat] | None = None
    # sha256 of the map file the overlay was made from (outdated detection).
    source_sha256: str | None = None
    accuracy_note: str | None = None
    # sha256 of the .points file used, so an edited points file triggers a rebuild.
    points_sha256: str | None = None


class SchemeRecord(_Model):
    id: str
    city_id: str
    authority: str
    scheme_type: SchemeType
    scheme_no: str
    name_en: str | None = None
    name_gu: str | None = None
    status: Status = "unknown"
    # The source site's own wording, e.g. "Submitted to Govt." (status is then "draft").
    status_label: str | None = None
    status_date: date | None = None
    source_page_url: str
    files: list[FileEntry] = Field(default_factory=list)
    overlay: Overlay = Field(default_factory=Overlay)
    first_seen: datetime
    last_changed: datetime
    last_checked: datetime
    removed_from_source: bool = False

    @property
    def source_id(self) -> str:
        return source_id(self.city_id, self.authority)

    @property
    def owner_key(self) -> str:
        return owner_key(self.city_id, self.authority, self.scheme_type)

    def current_files(self) -> list[FileEntry]:
        return [f for f in self.files if not f.superseded]


class CityFile(_Model):
    schema_version: int = SCHEMA_VERSION
    city_id: str
    generated_at: datetime
    schemes: list[SchemeRecord]


class CityEntry(_Model):
    id: str
    name_en: str
    name_gu: str
    scheme_count: int
    updated_at: datetime


class CatalogIndex(_Model):
    schema_version: int = SCHEMA_VERSION
    generated_at: datetime
    cities: list[CityEntry]
    # Optional (Milestone 6): newest app version published on GitHub Releases.
    latest_app_version: str | None = None
    latest_app_url: str | None = None


class SchemeChange(_Model):
    id: str
    what: list[ChangeWhat]


class RunChanges(_Model):
    run_at: datetime
    new: list[str] = Field(default_factory=list)
    changed: list[SchemeChange] = Field(default_factory=list)
    removed_from_source: list[str] = Field(default_factory=list)
    failed_sources: list[str] = Field(default_factory=list)

    @property
    def has_data_changes(self) -> bool:
        return bool(self.new or self.changed or self.removed_from_source)


class ChangesFile(_Model):
    schema_version: int = SCHEMA_VERSION
    runs: list[RunChanges] = Field(default_factory=list)


class SourceHealth(_Model):
    consecutive_failures: int = 0
    last_error: str | None = None
    last_success: datetime | None = None


class StatusFile(_Model):
    """Pipeline bookkeeping, published alongside the catalog but not used by the app."""

    sources: dict[str, SourceHealth] = Field(default_factory=dict)


# --------------------------------------------------------------------------- scraper output


class DiscoveredFile(_Model):
    kind: FileKind
    title: str
    url: str


class DiscoveredScheme(_Model):
    """What a scraper found on a source site. The pipeline turns it into a SchemeRecord."""

    city_id: str
    authority: str
    scheme_type: SchemeType
    scheme_no: str
    name_en: str | None = None
    name_gu: str | None = None
    status: Status = "unknown"
    status_label: str | None = None
    status_date: date | None = None
    source_page_url: str
    files: list[DiscoveredFile] = Field(default_factory=list)

    @property
    def id(self) -> str:
        from opennaksha.ids import make_scheme_id

        return make_scheme_id(
            self.city_id, self.authority, self.scheme_type, self.scheme_no, self.name_en
        )


def owner_key(city_id: str, authority: str, scheme_type: str) -> str:
    """Which scraper manages a record: authority + map type, e.g. ``surat-suda:DP``.

    One authority can have several scrapers (TP schemes, DP sheets, village maps). A scraper
    that succeeds may only mark *its own* records as removed from source.
    """
    return f"{source_id(city_id, authority)}:{scheme_type}"


def source_id(city_id: str, authority: str) -> str:
    """Identifier for one scraper/source, e.g. ``surat-smc``."""
    return f"{city_id}-{authority}".lower()
