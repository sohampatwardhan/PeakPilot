"""MassGIS loader tests (spec: .kiro/specs/test-framework, R4).

The loader reads only bundled CSVs. These tests pin the row counts and provenance
dates documented in data/DATA.md, check that missing values stay missing, and
check that loading works with the network disabled.
"""

from __future__ import annotations

import socket

import pytest

from peakpilot import massgis


def _clear_caches() -> None:
    massgis._utilities.cache_clear()
    massgis._landfills.cache_clear()


def test_counts_match_data_md():
    assert massgis.counts() == {"towns": 351, "landfill_projects": 116}


def test_towns_are_sorted_and_title_cased():
    towns = massgis.towns()
    assert towns == sorted(towns)
    assert "Boston" in towns
    assert all(t == t.title() for t in towns)


@pytest.mark.parametrize("query", ["Boston", "BOSTON", "boston", "  Boston  "])
def test_utility_lookup_ignores_case_and_whitespace(query):
    assert massgis.utility_for(query) == massgis.utility_for("BOSTON")
    assert massgis.utility_for(query)


def test_every_town_has_a_utility():
    for town in massgis.towns():
        assert massgis.utility_for(town), town


def test_unknown_town_returns_nothing():
    assert massgis.utility_for("Atlantis") is None
    assert massgis.landfills_for("Atlantis") == []


def test_landfill_lookup_ignores_case():
    assert massgis.landfills_for("acton") == massgis.landfills_for("ACTON")
    assert massgis.landfills_for("Acton")


def test_landfill_fields_are_typed():
    for p in massgis._landfills():
        assert isinstance(p, massgis.LandfillProject)
        assert p.town and p.site and p.type and p.status
        assert p.mw is None or (isinstance(p.mw, float) and p.mw >= 0)
        assert p.since is None or len(p.since) == 10  # ISO yyyy-mm-dd


def test_missing_values_load_as_none(repo_root):
    """Empty MW / SINCE in the CSV become None, never a guessed number or date."""
    import csv

    with (repo_root / "data" / "landfills.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    projects = massgis._landfills()
    assert len(rows) == len(projects)
    empty_mw = sum(1 for r in rows if not r["MW"].strip())
    empty_since = sum(1 for r in rows if not r["SINCE"].strip())
    assert sum(1 for p in projects if p.mw is None) == empty_mw
    assert sum(1 for p in projects if p.since is None) == empty_since


def test_unparseable_mw_loads_as_none(tmp_path, monkeypatch):
    (tmp_path / "landfills.csv").write_text(
        "TOWN,SITE,TYPE,MW,STATUS,SINCE\nTestville,Test LF,Solar,n/a,Permitted,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(massgis, "_DATA_DIR", tmp_path)
    _clear_caches()
    try:
        (p,) = massgis._landfills()
        assert p.mw is None and p.since is None
    finally:
        monkeypatch.undo()
        _clear_caches()


def test_loads_with_network_disabled(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("massgis attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    _clear_caches()
    try:
        assert massgis.counts()["towns"] == 351
    finally:
        _clear_caches()


def test_provenance_dates_match_data_md(repo_root):
    data_md = (repo_root / "data" / "DATA.md").read_text(encoding="utf-8")
    assert f"Portal snapshot date: {massgis.PORTAL_SNAPSHOT_DATE}" in data_md
    assert f"Retrieved:** {massgis.RETRIEVED_DATE}" in data_md
    assert "MassGIS" in massgis.SOURCE
