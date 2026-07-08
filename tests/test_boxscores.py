"""Tests for box-score gameid resolution (no network)."""
from datetime import date

from nzwihl_rosters import boxscores


SHELL = """
<a href="/leagues/stats_1team.cfm?clientID=7132&teamID=675638&leagueID=35501&printPage=0"><b>Dunedin Thunder</b></a>
<a href="/leagues/stats_1team.cfm?clientID=7132&teamID=675638&leagueID=35501&printPage=0"><b>DTW</b></a>
NZWIHL June 27th, 2026 7:00PM Queenstown
<a href="/leagues/stats_1team.cfm?clientID=7132&teamID=675639&leagueID=35501&printPage=0"><b>Wakatipu Wild</b></a>
<a href="/leagues/stats_1team.cfm?clientID=7132&teamID=675639&leagueID=35501&printPage=0"><b>WLD</b></a>
Game Number: 18
"""

SCHEDULE = """
[FINAL](https://www.nzwihl.com/leagues/hockey_boxscores.cfm?clientid=7132&leagueid=35501&gameid=2520015)
[FINAL](https://www.nzwihl.com/leagues/hockey_boxscores.cfm?clientid=7132&leagueid=35501&gameid=2520016)
SAT 27 JUN tickets only, no boxscore link yet
"""


def test_parse_shell_orders_away_then_home_and_reads_date():
    parsed = boxscores.parse_shell(SHELL)
    assert parsed == {"away_id": 675638, "home_id": 675639, "date": date(2026, 6, 27)}


def test_parse_shell_rejects_non_game_page():
    assert boxscores.parse_shell("<html>no teams here, June stuff</html>") is None


def test_last_final_gameid_picks_the_max():
    assert boxscores.last_final_gameid(SCHEDULE) == 2520016


def test_public_boxscore_url_shape():
    url = boxscores.public_boxscore_url(2520017)
    assert "hockey_boxscores.cfm" in url and "gameid=2520017" in url
    assert "clientid=7132" in url and "leagueid=35501" in url


def test_prune_and_merge_drops_entries_older_than_keep_days():
    today = date(2026, 7, 2)
    existing = [
        {"date": "2026-06-27", "datetime": "2026-06-27T19:00:00+12:00",
         "away": "Dunedin Thunder Women", "home": "Wakatipu Wild"},
    ]
    merged = boxscores.prune_and_merge(existing, [], keep_days=3, today=today)
    assert merged == []  # 5 days old, past the 3-day keep window


def test_prune_and_merge_keeps_recently_played_entries():
    today = date(2026, 7, 2)
    existing = [
        {"date": "2026-06-30", "datetime": "2026-06-30T19:00:00+12:00",
         "away": "Dunedin Thunder Women", "home": "Wakatipu Wild"},
    ]
    merged = boxscores.prune_and_merge(existing, [], keep_days=3, today=today)
    assert len(merged) == 1  # only 2 days old, still within the keep window


def test_prune_and_merge_new_games_replace_old_duplicate_and_sort():
    today = date(2026, 7, 2)
    existing = [
        {"date": "2026-07-04", "datetime": "2026-07-04T16:45:00+12:00",
         "away": "SkyCity Stampede", "home": "Botany Swarm", "gameid": None},
    ]
    new = [
        {"date": "2026-07-04", "datetime": "2026-07-04T16:45:00+12:00",
         "away": "SkyCity Stampede", "home": "Botany Swarm", "gameid": 2519941},
        {"date": "2026-07-05", "datetime": "2026-07-05T16:45:00+12:00",
         "away": "SkyCity Stampede", "home": "Botany Swarm", "gameid": 2519942},
    ]
    merged = boxscores.prune_and_merge(existing, new, keep_days=3, today=today)
    assert len(merged) == 2
    assert merged[0]["gameid"] == 2519941  # replaced, not duplicated
    assert merged[1]["date"] == "2026-07-05"


def test_resolve_marks_in_core_window_true_without_core_keys():
    """Back-compat: callers that don't pass core_keys (e.g. existing tests,
    single-window callers) get every game marked in_core_window=True."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from nzwihl_rosters.schedule import Game
    from nzwihl_rosters.teams import TEAMS

    steel = TEAMS["AUCKLAND STEEL"]
    inferno = TEAMS["CANTERBURY INFERNO"]
    g = Game(datetime(2026, 7, 10, 16, 45, tzinfo=ZoneInfo("Pacific/Auckland")),
              away=steel, home=inferno, venue="Test Arena", is_final=False)
    out = boxscores.resolve([g], SCHEDULE)
    assert out[0]["in_core_window"] is True


def test_resolve_marks_in_core_window_false_when_outside_core_keys():
    """Games outside the narrower PDF window (not in core_keys) are still
    included in the manifest but flagged in_core_window=False, so pages that
    want the old narrow behaviour (the portal) can filter them back out while
    hockeyrosters shows them as 'coming soon'."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from nzwihl_rosters.schedule import Game
    from nzwihl_rosters.teams import TEAMS

    steel = TEAMS["AUCKLAND STEEL"]
    inferno = TEAMS["CANTERBURY INFERNO"]
    near = Game(datetime(2026, 7, 6, 16, 45, tzinfo=ZoneInfo("Pacific/Auckland")),
                away=steel, home=inferno, venue="Test Arena", is_final=False)
    far = Game(datetime(2026, 7, 14, 16, 45, tzinfo=ZoneInfo("Pacific/Auckland")),
               away=inferno, home=steel, venue="Test Arena", is_final=False)
    core_keys = {(near.away.team_id, near.home.team_id, near.start_local)}
    out = boxscores.resolve([near, far], SCHEDULE, core_keys=core_keys)
    by_date = {o["date"]: o["in_core_window"] for o in out}
    assert by_date["2026-07-06"] is True
    assert by_date["2026-07-14"] is False


def test_last_final_gameid_lookback_fast_path_no_extra_calls():
    """If schedule_html already has a Final, the lookback must not make any
    extra network calls -- the common case stays exactly as cheap as before."""
    calls = []
    gid = boxscores._last_final_gameid_lookback(
        SCHEDULE, client_id=7132, league_id=35501,
        fetch_month=lambda m, y: calls.append((m, y)) or "unused")
    assert gid == 2520016
    assert calls == []


def test_last_final_gameid_lookback_falls_back_one_month():
    """Reproduces the 2026-07-08 bug: schedules.cfm's printPage view is scoped to
    the site's CURRENT server month. When a league's last Final game was in the
    PRIOR month (e.g. NZWIHL's June->July bye), the current month's schedule page
    has no boxscore link at all -- last_final_gameid() must walk backward and find
    June's Final (2520016) instead of silently giving up."""
    no_final_this_month = "SAT 11 JUL tickets only, no boxscore link yet"
    calls = []
    def fake_fetch_month(m, y):
        calls.append((m, y))
        return SCHEDULE if (m, y) == (6, 2026) else "nothing here either"

    gid = boxscores._last_final_gameid_lookback(
        no_final_this_month, client_id=7132, league_id=35501,
        today=date(2026, 7, 8), fetch_month=fake_fetch_month)
    assert gid == 2520016
    assert calls == [(6, 2026)]  # stopped as soon as a Final was found -- didn't over-fetch


def test_last_final_gameid_lookback_gives_up_after_max_months_back():
    """Bounded: must not loop forever (or walk back an entire season) if no
    recent month has a Final game at all."""
    calls = []
    def fake_fetch_month(m, y):
        calls.append((m, y))
        return "never any finals here"

    gid = boxscores._last_final_gameid_lookback(
        "also nothing", client_id=7132, league_id=35501,
        today=date(2026, 7, 8), max_months_back=3, fetch_month=fake_fetch_month)
    assert gid is None
    assert calls == [(6, 2026), (5, 2026), (4, 2026)]


def test_last_final_gameid_lookback_handles_year_rollover():
    """Walking back from January must cross into December of the prior year."""
    calls = []
    def fake_fetch_month(m, y):
        calls.append((m, y))
        return SCHEDULE if (m, y) == (12, 2025) else "nothing"

    gid = boxscores._last_final_gameid_lookback(
        "nothing this month", client_id=7132, league_id=35501,
        today=date(2026, 1, 15), max_months_back=3, fetch_month=fake_fetch_month)
    assert gid == 2520016
    assert calls == [(12, 2025)]
