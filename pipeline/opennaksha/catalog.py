"""Read the previous catalog and write a new one (PLAN.md §5, §6 steps 1 and 6)."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from opennaksha.cities import get_city
from opennaksha.models import (
    CatalogIndex,
    ChangesFile,
    CityEntry,
    CityFile,
    RunChanges,
    SchemeRecord,
    StatusFile,
)

log = logging.getLogger(__name__)

MAX_RUNS = 20
_TYPE_ORDER = {"TP": 0, "DP": 1, "LAP": 2, "VILLAGE": 3}


@dataclass
class PreviousCatalog:
    schemes: dict[str, SchemeRecord] = field(default_factory=dict)
    changes: ChangesFile = field(default_factory=ChangesFile)
    status: StatusFile = field(default_factory=StatusFile)
    index: CatalogIndex | None = None

    @property
    def is_first_run(self) -> bool:
        return self.index is None


def load_previous(folder: Path | None) -> PreviousCatalog:
    """Load a catalog folder (the checked-out ``catalog`` branch). Missing → first run."""
    prev = PreviousCatalog()
    if folder is None:
        return prev
    cat = folder / "catalog"
    index_file = cat / "index.json"
    if not index_file.exists():
        log.info("no previous catalog at %s, treating as first run", folder)
        return prev
    prev.index = CatalogIndex.model_validate_json(index_file.read_bytes())
    for city_file in sorted((cat / "cities").glob("*.json")):
        data = CityFile.model_validate_json(city_file.read_bytes())
        for s in data.schemes:
            prev.schemes[s.id] = s
    if (cat / "changes.json").exists():
        prev.changes = ChangesFile.model_validate_json((cat / "changes.json").read_bytes())
    if (cat / "status.json").exists():
        prev.status = StatusFile.model_validate_json((cat / "status.json").read_bytes())
    return prev


def scheme_sort_key(s: SchemeRecord) -> tuple:
    # Natural sort: "TP 2" before "TP 10"; "12A" after "12".
    parts = re.split(r"(\d+)", s.scheme_no)
    natural = tuple((0, int(p), "") if p.isdigit() else (1, 0, p.lower()) for p in parts if p)
    return (_TYPE_ORDER.get(s.scheme_type, 9), natural, s.id)


def build_index(schemes: dict[str, SchemeRecord], now: datetime) -> CatalogIndex:
    by_city: dict[str, list[SchemeRecord]] = defaultdict(list)
    for s in schemes.values():
        by_city[s.city_id].append(s)
    cities = []
    for city_id in sorted(by_city):
        city = get_city(city_id)
        items = by_city[city_id]
        cities.append(
            CityEntry(
                id=city_id,
                name_en=city.name_en,
                name_gu=city.name_gu,
                scheme_count=sum(1 for s in items if not s.removed_from_source),
                updated_at=max(s.last_changed for s in items),
            )
        )
    return CatalogIndex(generated_at=now, cities=cities)


def write_catalog(
    out: Path,
    schemes: dict[str, SchemeRecord],
    changes: ChangesFile,
    status: StatusFile,
    now: datetime,
    latest_app_version: str | None = None,
    latest_app_url: str | None = None,
) -> CatalogIndex:
    """Write index.json, cities/*.json, changes.json and status.json (compact JSON)."""
    cat = out / "catalog"
    cities_dir = cat / "cities"
    cities_dir.mkdir(parents=True, exist_ok=True)
    for old in cities_dir.glob("*.json"):
        old.unlink()

    index = build_index(schemes, now)
    index.latest_app_version = latest_app_version
    index.latest_app_url = latest_app_url
    by_city: dict[str, list[SchemeRecord]] = defaultdict(list)
    for s in schemes.values():
        by_city[s.city_id].append(s)
    for city_id, items in by_city.items():
        city_file = CityFile(
            city_id=city_id, generated_at=now, schemes=sorted(items, key=scheme_sort_key)
        )
        _write(cities_dir / f"{city_id}.json", city_file.model_dump_json())
    _write(cat / "index.json", index.model_dump_json())
    _write(cat / "changes.json", changes.model_dump_json())
    _write(cat / "status.json", status.model_dump_json())
    return index


def append_run(changes: ChangesFile, run: RunChanges) -> ChangesFile:
    """Record a run in changes.json (newest first), keeping the last ``MAX_RUNS``.

    Runs where nothing happened are not recorded.
    """
    if not run.has_data_changes and not run.failed_sources:
        return changes
    return ChangesFile(runs=[run, *changes.runs][:MAX_RUNS])


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def folder_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0
