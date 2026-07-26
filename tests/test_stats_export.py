"""Tests for stats.json export (no network — fixture-driven). Ported from
the NZIHL sibling's test_stats_export.py."""
import json
from pathlib import Path

from nzwihl_rosters.scraper import parse_skaters, parse_goalies
from nzwihl_rosters import stats_export

FIXTURES = Path(__file__).parent / "fixtures"


def test_skater_dict_shape_and_pts_derivation():
    html = (FIXTURES / "team_dtw_v2cols.html").read_text()
    skaters = parse_skaters(html, team_id=675638)
    d = stats_export._skater_dict(skaters[0], game_logs={})
    assert set(d) == {"number", "first", "last", "position", "flag", "gp", "g", "a", "pts", "pim", "player_id"}
    assert d["pts"] == d["g"] + d["a"]


def test_skater_dict_falls_back_to_scraped_gA_when_warehouse_has_no_entry():
    """An empty (or non-matching) game_logs dict must not change anything —
    stats.json still reports the stats_1team.cfm-scraped G/A for a player the
    warehouse has never heard of (a network hiccup, or a player who genuinely
    hasn't recorded a goal/assist yet, both look the same here)."""
    html = (FIXTURES / "team_dtw_v2cols.html").read_text()
    skaters = parse_skaters(html, team_id=675638)
    row = skaters[0]
    d = stats_export._skater_dict(row, game_logs={})
    assert d["g"] == row.g
    assert d["a"] == row.a


def test_skater_dict_prefers_warehouse_gA_when_matched():
    """When the raw scraped name normalizes to a warehouse key, that entry's
    summed goals/assists win over the scraped row's own G/A columns — this is
    the whole point of the 2026-07-13 migration (see stats_export.py's
    module docstring)."""
    html = (FIXTURES / "team_dtw_v2cols.html").read_text()
    skaters = parse_skaters(html, team_id=675638)
    row = skaters[0]
    key = stats_export._normalize_name(row.raw_name)
    game_logs = {key: {"name": row.raw_name, "teamID": 675638,
                        "games": [{"gameid": 1, "date": "2026-05-01", "goals": 9, "assists": 1},
                                  {"gameid": 2, "date": "2026-05-08", "goals": 1, "assists": 2}]}}
    d = stats_export._skater_dict(row, game_logs=game_logs)
    assert d["g"] == 10
    assert d["a"] == 3
    assert d["pts"] == 13


def test_warehouse_goals_assists_matches_raw_name_with_parenthetical():
    """Guards the exact scenario that made a raw (un-overridden) name the
    right lookup key: a player whose title="..." text carries a
    parenthetical maiden name/nickname (e.g. Canterbury Inferno's Reagyn
    Shattock) is stored verbatim, parens and all, in the warehouse's
    player_game_logs -- normalizing the override-CORRECTED name (which
    strips the parenthetical for display) would miss this entry entirely."""
    raw = "Reagyn Shattock (Niskakoski)"
    game_logs = {
        stats_export._normalize_name(raw): {
            "name": raw, "teamID": 675637,
            "games": [{"gameid": 1, "date": "2026-05-01", "goals": 4, "assists": 1}],
        }
    }
    result = stats_export._warehouse_goals_assists(raw, game_logs)
    assert result == (4, 1)
    # The override-corrected display name (no parenthetical) must NOT match —
    # this is exactly why the raw name is used as the lookup key.
    assert stats_export._warehouse_goals_assists("Reagyn Shattock", game_logs) is None


def test_goalie_dict_shape():
    html = (FIXTURES / "team_dtw_v2cols.html").read_text()
    goalies = parse_goalies(html, team_id=675638)
    d = stats_export._goalie_dict(goalies[0])
    assert set(d) == {"number", "first", "last", "flag", "gp", "min", "ga", "gaa", "sv_pct", "so", "w", "l", "player_id"}


def test_write_stats_json_shape(tmp_path):
    fake_teams = {"CIN": {"team_id": 675637, "display_name": "Canterbury Inferno",
                           "skaters": [], "goalies": [], "coaches": []}}
    out = tmp_path / "stats.json"
    payload = stats_export.write_stats_json(out, league_key="nzwihl", teams_stats=fake_teams)
    assert payload["league"] == "nzwihl"
    assert "generated_at" in payload
    assert payload["teams"] == fake_teams
    on_disk = json.loads(out.read_text())
    assert on_disk == payload


def test_scrape_all_teams_stats_skips_a_failing_team(monkeypatch):
    from nzwihl_rosters.teams import TEAMS

    def fake_scrape_team_stats(team, client_id, league_id, game_logs):
        if team.short_code == "CIN":
            raise RuntimeError("simulated network failure")
        return {"team_id": team.team_id, "display_name": team.display_name,
                "skaters": [], "goalies": [], "coaches": []}

    # No network for the warehouse fetch either — this file is fixture-driven.
    monkeypatch.setattr(stats_export, "fetch_player_game_logs", lambda: {})
    monkeypatch.setattr(stats_export, "scrape_team_stats", fake_scrape_team_stats)
    out = stats_export.scrape_all_teams_stats()
    assert "CIN" not in out
    assert len(out) == len(TEAMS) - 1


def test_scrape_all_teams_stats_degrades_gracefully_when_warehouse_fetch_fails(monkeypatch):
    """A broken/unreachable nzihl-season-data warehouse must not take down
    stats.json at all — every team still gets scraped, just with G/A/PTS
    sourced from stats_1team.cfm as before this migration."""
    from nzwihl_rosters.teams import TEAMS

    def fake_scrape_team_stats(team, client_id, league_id, game_logs):
        assert game_logs == {}  # the degraded (empty) fallback, not a real fetch
        return {"team_id": team.team_id, "display_name": team.display_name,
                "skaters": [], "goalies": [], "coaches": []}

    def fake_fetch_player_game_logs():
        raise RuntimeError("simulated warehouse outage")

    monkeypatch.setattr(stats_export, "fetch_player_game_logs", fake_fetch_player_game_logs)
    monkeypatch.setattr(stats_export, "scrape_team_stats", fake_scrape_team_stats)
    out = stats_export.scrape_all_teams_stats()
    assert len(out) == len(TEAMS)
