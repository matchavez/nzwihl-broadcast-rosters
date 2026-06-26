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
