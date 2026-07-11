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
    assert upcoming[0].venue == "Paradice Avondale"
    assert upcoming[1].venue == "Paradice Botany"
    assert upcoming[2].venue == "Queenstown Ice Arena"


def test_final_game_parsed():
    html = (FIXTURES / "schedule_min.html").read_text()
    games = parse_schedule(html)
    final = [g for g in games if g.is_final][0]
    assert final.away.short_code == "AST"
    assert final.home.short_code == "WLD"
    assert final.start_local.year == 2026


from nzwihl_rosters.scraper import parse_skaters, parse_goalies


def test_skaters_parse_correctly():
    html = (FIXTURES / "team_dtw_min.html").read_text()
    skaters = parse_skaters(html, team_id=675638)
    by_num = {s.jersey: s for s in skaters}

    daigle = by_num["19"]
    assert daigle.first == "Justin"
    assert daigle.last == "DAIGLE"
    assert daigle.gp == 4 and daigle.g == 5 and daigle.a == 3
    assert daigle.flag == "IM"
    assert daigle.position == "F"

    # Lowercase auto-title-casing: "ashley reid" -> "Ashley" / "REID"
    reid = by_num["81"]
    assert reid.first == "Ashley"
    assert reid.last == "REID"

    # RO flag preserved
    fox = by_num["4"]
    assert fox.flag == "RO"
    assert fox.gp == 0


def test_skaters_parse_correctly_with_extra_columns():
    """Regression test (ported from NZIHL): a stats_1team.cfm revision that
    inserts a BY (birth year) column — and appends P/G, +/-, PPG, etc. —
    must not shift GP/G/A off by one. Columns are located by header label,
    not a fixed offset."""
    html = (FIXTURES / "team_dtw_v2cols.html").read_text()
    skaters = parse_skaters(html, team_id=675638)
    by_num = {s.jersey: s for s in skaters}

    daigle = by_num["19"]
    assert daigle.gp == 12 and daigle.g == 20 and daigle.a == 11
    assert daigle.position == "F"
    assert daigle.plus_minus == "13"

    brooks = by_num["8"]
    assert brooks.gp == 12 and brooks.g == 1 and brooks.a == 4
    assert brooks.plus_minus == "-7"
    assert brooks.flag == "C"

    park = by_num["7"]
    assert park.plus_minus == "E"


def test_skaters_plus_minus_blank_when_column_absent():
    """The original (no BY, no +/-) layout must still parse cleanly, with
    plus_minus defaulting to blank rather than erroring or misreading PTS."""
    html = (FIXTURES / "team_dtw_min.html").read_text()
    skaters = parse_skaters(html, team_id=675638)
    assert all(s.plus_minus == "" for s in skaters)


def test_goalies_parse_correctly():
    html = (FIXTURES / "team_dtw_min.html").read_text()
    goalies = parse_goalies(html, team_id=675638)
    by_num = {g.jersey: g for g in goalies}
    assert len(goalies) == 4

    sharp = by_num["52"]
    assert sharp.first == "Nina"
    assert sharp.last == "SHARP"
    assert sharp.gp == 1
    assert sharp.gaa == "3.93"
    assert sharp.sv_pct == ".920"


def test_goalies_parse_correctly_with_extra_by_column():
    """Regression test (ported from NZIHL): a stats_1team.cfm revision that
    inserts a BY (birth year) column between "#" and "GP" in the GOALIE
    STATISTICS table must not zero out GP."""
    html = (FIXTURES / "team_dtw_v2cols.html").read_text()
    goalies = parse_goalies(html, team_id=675638)
    assert len(goalies) == 1
    sharp = goalies[0]
    assert sharp.jersey == "52"
    assert sharp.gp == 1, f"expected gp=1, got {sharp.gp!r} (BY column likely misread as GP)"
    assert sharp.mp == 61
    assert sharp.gaa == "3.93"
    assert sharp.sv_pct == ".920"


def test_goalies_parse_correctly_with_broken_tooltip_header():
    """Regression test (ported from NZIHL): the live GOALIE STATISTICS table
    wraps header labels in `<span title="...">` tooltips, and the GAA
    tooltip's title attribute embeds a literal `<br />`. A naive
    tag-stripping regex treats that embedded `<`/`>` as a real tag boundary,
    garbling the cleaned "GAA" label so the header lookup misses it and
    silently falls back to the wrong column (GA's index)."""
    html = (FIXTURES / "team_steel_broken_tooltip.html").read_text()
    goalies = parse_goalies(html, team_id=675636)
    by_num = {g.jersey: g for g in goalies}

    yates = by_num["35"]
    assert yates.gp == 5 and yates.mp == 301
    assert yates.gaa == "3.19", f"expected gaa=3.19, got {yates.gaa!r} (GAA tooltip likely misparsed as GA)"
    assert yates.sv_pct == ".905"

    ashe = by_num["39"]
    assert ashe.gp == 5 and ashe.mp == 301
    assert ashe.gaa == "3.39", f"expected gaa=3.39, got {ashe.gaa!r}"
    assert ashe.sv_pct == ".909"


def test_coaches_parse_correctly():
    from nzwihl_rosters.scraper import parse_coaches
    html = (FIXTURES / "personnel_steel_min.html").read_text()
    coaches = parse_coaches(html)
    assert len(coaches) == 3
    assert [c.title for c in coaches] == ["Head Coach", "Assistant Coach", "Assistant Coach"]

    head = coaches[0]
    assert head.first == "Darren" and head.last == "Blong"

    assistants = coaches[1:]
    assert {(a.first, a.last) for a in assistants} == {("Markku", "Multaharju"), ("Rachel", "Park")}


def test_coaches_parse_empty_when_none_listed():
    from nzwihl_rosters.scraper import parse_coaches
    html = (FIXTURES / "personnel_no_coaches_min.html").read_text()
    assert parse_coaches(html) == []
