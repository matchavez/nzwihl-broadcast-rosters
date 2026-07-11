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
    d = stats_export._skater_dict(skaters[0])
    assert set(d) == {"number", "first", "last", "position", "flag", "gp", "g", "a", "pts", "pim"}
    assert d["pts"] == d["g"] + d["a"]


def test_goalie_dict_shape():
    html = (FIXTURES / "team_dtw_v2cols.html").read_text()
    goalies = parse_goalies(html, team_id=675638)
    d = stats_export._goalie_dict(goalies[0])
    assert set(d) == {"number", "first", "last", "flag", "gp", "min", "ga", "gaa", "sv_pct", "so", "w", "l"}


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

    def fake_scrape_team_stats(team, client_id, league_id):
        if team.short_code == "CIN":
            raise RuntimeError("simulated network failure")
        return {"team_id": team.team_id, "display_name": team.display_name,
                "skaters": [], "goalies": [], "coaches": []}

    monkeypatch.setattr(stats_export, "scrape_team_stats", fake_scrape_team_stats)
    out = stats_export.scrape_all_teams_stats()
    assert "CIN" not in out
    assert len(out) == len(TEAMS) - 1
