"""CLI entry point: ``uv run python -m opennaksha.run``.

The run flow (PLAN.md §6) is implemented in Milestone 2. For now this only parses arguments.
"""

import argparse
import sys
from pathlib import Path

from opennaksha import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="opennaksha.run", description=__doc__)
    p.add_argument("--city", help="run only the scrapers for this city id (e.g. surat)")
    p.add_argument("--previous", type=Path, help="folder holding the previous catalog to diff with")
    p.add_argument("--output", type=Path, default=Path("output"), help="output folder")
    p.add_argument("--no-download", action="store_true", help="metadata only, skip file hashing")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"opennaksha {__version__}: no scrapers yet (Milestone 2). args={vars(args)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
