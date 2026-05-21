"""Parse the NZWIHL schedule page into a list of upcoming games.

The schedules.cfm page uses a flat table structure (no h5 date headers):

  <tr>
    <td>4:30 PM</td>                      ← time; "Final" link for played games
    <td>May. 23, 2026 @ 4:30 PM</td>      ← full date + time
    <td><a href="...teamID=675638...">Dunedin Thunder DTW</a></td>  ← away
    <td>&nbsp;</td>                        ← away score (or &nbsp; upcoming)
    <td><a href="...teamID=675636...">Auckland Steel AST</a></td>   ← home
    <td>&nbsp;</td>                        ← home score (or &nbsp; upcoming)
    <td>Avondale, Auckland</td>            ← venue (varies per game)
    <td>RS</td>
  </tr>

We parse by extracting the teamID from stats_1team.cfm links — the venue is
taken directly from td[6] since some teams rotate between venues.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html import unescape
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .http import fetch
from .teams import Team, by_team_id


SCHEDULE_URL = "https://www.nzwihl.com/leagues/schedules.cfm"
NZ_TZ = ZoneInfo("Pacific/Auckland")


@dataclass
class Game:
    start_local: datetime
    away: Team
    home: Team
    venue: str
    is_final: bool
    away_score: int | None = None
    home_score: int | None = None

    @property
    def matchup_slug(self) -> str:
        return f"{self.home.short_code}-vs-{self.away.short_code}"


def fetch_schedule_html(client_id: int = 7132, league_id: int = 35501) -> str:
    params = {"clientid": client_id, "leagueid": league_id, "schedType": "main", "printPage": 1}
    url = f"{SCHEDULE_URL}?{urlencode(params)}"
    return fetch(url)


_TR_RE = re.compile(r"<tr[^>]*>([\s\S]*?)</tr>", re.IGNORECASE)
_TD_RE = re.compile(r"<td[^>]*>([\s\S]*?)</td>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")

_TEAM_LINK_RE = re.compile(r'stats_1team\.cfm\?[^"\'<>]*teamID=(\d+)', re.IGNORECASE)
_BOXSCORE_RE = re.compile(r"hockey_boxscores\.cfm", re.IGNORECASE)

# "May. 23, 2026 @ 4:30 PM"
_DATE_RE = re.compile(
    r"(\w+)\.?\s+(\d{1,2}),\s+(\d{4})\s+@\s+(\d{1,2}):(\d{2})\s*(AM|PM)",
    re.IGNORECASE,
)

_MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}


def _clean(td_html: str) -> str:
    return unescape(_TAG_RE.sub("", td_html)).strip()


def _row_team_ids(row_html: str) -> list[int]:
    seen: list[int] = []
    for m in _TEAM_LINK_RE.finditer(row_html):
        tid = int(m.group(1))
        if tid not in seen:
            seen.append(tid)
    return seen


def parse_schedule(html: str) -> list[Game]:
    games: list[Game] = []

    for tr_match in _TR_RE.finditer(html):
        row_html = tr_match.group(1)

        team_ids = _row_team_ids(row_html)
        if len(team_ids) < 2:
            continue

        away = by_team_id(team_ids[0])
        home = by_team_id(team_ids[1])
        if not (away and home):
            continue

        cells = [_clean(td) for td in _TD_RE.findall(row_html)]
        if len(cells) < 6:
            continue

        # Date+time in cells[1]: "May. 23, 2026 @ 4:30 PM"
        date_m = _DATE_RE.search(cells[1] if len(cells) > 1 else "")
        if not date_m:
            continue

        month = _MONTHS.get(date_m.group(1).lower().rstrip("."))
        if not month:
            continue
        day = int(date_m.group(2))
        year = int(date_m.group(3))
        hour = int(date_m.group(4))
        minute = int(date_m.group(5))
        ampm = date_m.group(6).upper()
        if ampm == "PM" and hour != 12:
            hour += 12
        if ampm == "AM" and hour == 12:
            hour = 0

        is_final = bool(_BOXSCORE_RE.search(row_html))

        venue = cells[6] if len(cells) > 6 else home.home_venue

        if is_final:
            start_local = datetime(year, month, day, 12, 0, tzinfo=NZ_TZ)
            try:
                away_score = int(cells[3]) if cells[3] not in ("", "\xa0", "-") else None
                home_score = int(cells[5]) if cells[5] not in ("", "\xa0", "-") else None
            except ValueError:
                away_score = home_score = None
            games.append(Game(start_local, away, home, venue, True, away_score, home_score))
        else:
            start_local = datetime(year, month, day, hour, minute, tzinfo=NZ_TZ)
            games.append(Game(start_local, away, home, venue, False))

    return games


def upcoming_within(days: int, html: str | None = None) -> list[Game]:
    if html is None:
        html = fetch_schedule_html()
    games = parse_schedule(html)
    now = datetime.now(NZ_TZ)
    cutoff = now + timedelta(days=days)
    return [g for g in games if (not g.is_final) and now <= g.start_local <= cutoff]


def group_into_series(games: list[Game]) -> list[list[Game]]:
    """Group games between the same two teams into a series."""
    by_key: dict[tuple[int, int], list[list[Game]]] = {}
    for g in sorted(games, key=lambda x: x.start_local):
        key = tuple(sorted([g.away.team_id, g.home.team_id]))
        groups = by_key.setdefault(key, [])
        if groups and (g.start_local - groups[-1][-1].start_local) <= timedelta(days=3):
            groups[-1].append(g)
        else:
            groups.append([g])
    out: list[list[Game]] = []
    for groups in by_key.values():
        out.extend(groups)
    out.sort(key=lambda s: s[0].start_local)
    return out
