"""Parse an NZWIHL stats_1team.cfm HTML page into player + goalie lists."""
from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlencode

from .http import fetch
from .overrides import normalize_name


STATS_URL = "https://www.nzwihl.com/leagues/stats_1team.cfm"

_PLAYER_LINK = re.compile(
    r'<a[^>]*href="[^"]*playerID=(\d+)[^"]*"[^>]*title="([^"]+)"[^>]*>'
)


@dataclass
class SkaterRow:
    jersey: str
    last: str
    first: str
    position: str
    gp: int
    g: int
    a: int
    flag: str


@dataclass
class GoalieRow:
    jersey: str
    last: str
    first: str
    gp: int
    gaa: str
    sv_pct: str
    flag: str


def fetch_team_html(team_id: int, client_id: int = 7132, league_id: int = 35501) -> str:
    params = {"clientid": client_id, "leagueid": league_id, "teamid": team_id}
    url = f"{STATS_URL}?{urlencode(params)}"
    return fetch(url)


def _split_first_last(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) == 1:
        return ("", parts[0])
    if len(parts) == 2:
        return (parts[0], parts[1])
    multi_word: set[str] = set()
    tail2 = " ".join(parts[-2:]).lower()
    if tail2 in multi_word:
        return (" ".join(parts[:-2]), " ".join(parts[-2:]))
    return (" ".join(parts[:-1]), parts[-1])


_PLAYER_STATS_RE = re.compile(r"PLAYER STATISTICS[\s\S]*?TEAM TOTALS", re.IGNORECASE)
_GOALIE_STATS_RE = re.compile(r"GOALIE STATISTICS[\s\S]*?TEAM TOTALS", re.IGNORECASE)
_TR_RE = re.compile(r"<tr[^>]*>([\s\S]*?)</tr>", re.IGNORECASE)
_TD_RE = re.compile(r"<td[^>]*>([\s\S]*?)</td>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(td_html: str) -> str:
    return unescape(_TAG_RE.sub("", td_html)).strip()


def _row_flag(row_html: str) -> str:
    for td in _TD_RE.findall(row_html):
        if "<a" in td:
            text = _clean(td)
            tail = text.split()[-1] if text else ""
            if tail in {"C", "A", "IM", "AF", "RO"}:
                return tail
            return ""
    return ""


def _player_full_name(row_html: str) -> str | None:
    m = _PLAYER_LINK.search(row_html)
    if not m:
        return None
    return m.group(2)


def parse_skaters(html: str, team_id: int) -> list[SkaterRow]:
    block = _PLAYER_STATS_RE.search(html)
    if not block:
        return []
    rows: list[SkaterRow] = []
    for row_match in _TR_RE.finditer(block.group(0)):
        row_html = row_match.group(1)
        full_name = _player_full_name(row_html)
        if not full_name:
            continue
        cells = [_clean(td) for td in _TD_RE.findall(row_html)]
        if len(cells) < 7:
            continue
        jersey = cells[2] or "-"
        position = cells[3] or ""
        try:
            gp = int(cells[4]) if cells[4] not in ("", "-") else 0
            g = int(cells[5]) if cells[5] not in ("", "-") else 0
            a = int(cells[6]) if cells[6] not in ("", "-") else 0
        except ValueError:
            continue
        first_raw, last_raw = _split_first_last(full_name)
        first, last = normalize_name(first_raw, last_raw, team_id, jersey)
        flag = _row_flag(row_html)
        rows.append(SkaterRow(
            jersey=jersey, last=last.upper() if last else "",
            first=first, position=position,
            gp=gp, g=g, a=a, flag=flag,
        ))
    return rows


def parse_goalies(html: str, team_id: int) -> list[GoalieRow]:
    block = _GOALIE_STATS_RE.search(html)
    if not block:
        return []
    rows: list[GoalieRow] = []
    for row_match in _TR_RE.finditer(block.group(0)):
        row_html = row_match.group(1)
        full_name = _player_full_name(row_html)
        if not full_name:
            continue
        cells = [_clean(td) for td in _TD_RE.findall(row_html)]
        if len(cells) < 16:
            continue
        jersey = cells[2] or "-"
        try:
            gp = int(cells[3]) if cells[3] not in ("", "-") else 0
        except ValueError:
            gp = 0
        gaa = cells[11] or "—"
        sv_pct = cells[15] or "—"
        first_raw, last_raw = _split_first_last(full_name)
        first, last = normalize_name(first_raw, last_raw, team_id, jersey)
        flag = _row_flag(row_html)
        rows.append(GoalieRow(
            jersey=jersey, last=last.upper() if last else "",
            first=first, gp=gp, gaa=gaa, sv_pct=sv_pct, flag=flag,
        ))
    return rows


def scrape_team(team_id: int, html: str | None = None) -> tuple[list[SkaterRow], list[GoalieRow]]:
    if html is None:
        html = fetch_team_html(team_id)
    return parse_skaters(html, team_id), parse_goalies(html, team_id)
