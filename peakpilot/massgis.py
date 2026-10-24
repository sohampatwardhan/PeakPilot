"""Load bundled MassGIS context data (public facts, never simulation output).

This module reads only from the bundled ``data/*.csv`` snapshots — it makes no
network calls at runtime, so the demo is dependable offline. The values here are
public Massachusetts infrastructure facts and must always be presented separately
from PeakPilot's SIMULATED device telemetry.

Honesty constraints (see ``data/DATA.md``): reported landfill capacity in MW is not
generation; this data does not establish grid demand, capacity, price, carbon
intensity, or which generator supplies a building.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Snapshot provenance surfaced in the UI (see data/DATA.md).
SOURCE = "MassGIS (Commonwealth of Massachusetts), via Hackachusetts 2026 climate kit"
PORTAL_SNAPSHOT_DATE = "2026-10-18"
RETRIEVED_DATE = "2026-10-24"


@dataclass(frozen=True)
class LandfillProject:
    """One renewable project sited on a Massachusetts landfill (public fact).

    ``mw`` is reported capacity in megawatts (operating value preferred, else
    permitted); it is NOT actual generation. ``None`` means the source reported no
    value. ``since`` is an ISO operating-since date or ``None``.
    """

    town: str
    site: str
    type: str
    mw: float | None
    status: str
    since: str | None


@lru_cache(maxsize=1)
def _utilities() -> dict[str, str]:
    """Return ``{TOWN (upper-case): utility name}`` from the bundled snapshot."""
    path = _DATA_DIR / "utilities.csv"
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            town = (row.get("TOWN") or "").strip()
            if town:
                out[town.upper()] = (row.get("UTILITY") or "").strip()
    return out


@lru_cache(maxsize=1)
def _landfills() -> tuple[LandfillProject, ...]:
    """Return all landfill renewable projects from the bundled snapshot."""
    path = _DATA_DIR / "landfills.csv"
    projects: list[LandfillProject] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            town = (row.get("TOWN") or "").strip()
            mw_raw = (row.get("MW") or "").strip()
            try:
                mw = float(mw_raw) if mw_raw else None
            except ValueError:
                mw = None
            since = (row.get("SINCE") or "").strip() or None
            projects.append(
                LandfillProject(
                    town=town,
                    site=(row.get("SITE") or "").strip(),
                    type=(row.get("TYPE") or "").strip(),
                    mw=mw,
                    status=(row.get("STATUS") or "").strip(),
                    since=since,
                )
            )
    return tuple(projects)


def towns() -> list[str]:
    """Sorted list of Massachusetts town names (title-cased for display)."""
    return sorted(t.title() for t in _utilities().keys())


def utility_for(town: str) -> str | None:
    """Return the listed electric utility for ``town``, or ``None`` if unknown."""
    return _utilities().get(town.strip().upper())


def landfills_for(town: str) -> list[LandfillProject]:
    """Return listed landfill renewable projects in ``town`` (may be empty)."""
    key = town.strip().upper()
    return [p for p in _landfills() if p.town.upper() == key]


def counts() -> dict[str, int]:
    """Row counts for display/verification."""
    return {"towns": len(_utilities()), "landfill_projects": len(_landfills())}
