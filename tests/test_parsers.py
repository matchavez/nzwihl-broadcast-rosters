"""Parser tests against hand-crafted HTML fixtures."""
from __future__ import annotations

from pathlib import Path

from nzwihl_rosters.schedule import parse_schedule
from nzwihl_rosters.teams import TEAMS

FIXTURES = Path(__file__).parent / "fixtures"


def test_teams_registry():
    assert "AUCKLAND STEEL" in TEAMS
    assert "CANTERBURY INFERNO" in TEAMS
    assert "DUNEDIN THUNDER WOMEN" in TEAMS
    assert "WAKATIPU WILD" in TEAMS
    for team in TEAMS.values():
        assert team.team_id > 0
        assert team.short_code
        assert team.primary_hex.startswith("#")


def test_schedule_parses_upcoming_only():
    html = (FIXTURES / "schedule_min.html").read_text()
    games = parse_schedule(html)
    assert len(games) == 4, f"expected 4 games, got {len(games)}"

    finals = [g for g in games if g.is_final]
    upcoming = [g for g in games if not g.is_final]
    assert len(finals) == 1
    assert len(upcoming) == 3


def test_schedule_team_identity():
    html = (FIXTURES / "schedule_min.html").read_text()
    games = parse_schedule(html)
    upcoming = [g for g in games if not g.is_final]

    # First two upcoming: DTW away at AST home (May 23 and 24)
    assert upcoming[0].away.short_code == "DTW"
    assert upcoming[0].home.short_code == "AST"
    assert upcoming[0].start_local.strftime("%Y-%m-%d %H:%M") == "2026-05-23 16:30"

    assert upcoming[1].away.short_code == "DTW"
    assert upcoming[1].home.short_code == "AST"
    assert upcoming[1].start_local.strftime("%Y-%m-%d") == "2026-05-24"


def test_schedule_venue_per_row():
    html = (FIXTURES / "schedule_min.html").read_text()
    games = parse_schedule(html)
    upcoming = [g for g in games if not g.is_final]

    # Same home team, different venues
    assert upcoming[0].venue == "Avondale, Auckland"
    assert upcoming[1].venue == "Botany, Auckland"
    assert upcoming[2].venue == "Queenstown"


def test_final_game_parsed():
    html = (FIXTURES / "schedule_min.html").read_text()
    games = parse_schedule(html)
    final = [g for g in games if g.is_final][0]
    assert final.away.short_code == "AST"
    assert final.home.short_code == "WLD"
    assert final.start_local.year == 2026
