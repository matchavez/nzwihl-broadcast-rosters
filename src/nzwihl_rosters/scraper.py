"""Parse an NZWIHL stats_1team.cfm HTML page into player + goalie lists.

The page is server-rendered HTML with two tables we care about:
PLAYER STATISTICS and GOALIE STATISTICS. Each player row contains
the jersey number, position, GP, G, A, and any flag (C / IM / AF / RO).
We parse with regex against the link-wrapped player cells since the
table cell structure is consistent across all four teams.

NZWIHL shares the same admin.esportsdesk.com stats_1team.cfm platform as
NZIHL, so it is subject to the identical header-drift and tooltip-markup
issues NZIHL hit — the fixes below are ported straight across rather than
waiting for NZWIHL to reproduce the same bug independently (Mat, 2026-07-05).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlencode

from .http import fetch
from .overrides import normalize_name


STATS_URL = "https://admin.esportsdesk.com/leagues/stats_1team.cfm"

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
    flag: str  # "" / "C" / "A" / "IM" / "AF" / "RO"
    plus_minus: str = ""   # "" if the page revision doesn't carry a +/- column


@dataclass
class GoalieRow:
    jersey: str
    last: str
    first: str
    gp: int
    gaa: str
    sv_pct: str
    flag: str
    mp: int = 0


@dataclass
class CoachRow:
    """One coaching-staff entry from personnel.cfm. Only Head Coach /
    Assistant Coach rows are kept — personnel.cfm also lists front-office
    roles (Team Staff, Physio, General Manager, Team Lead) that aren't
    coaches and aren't in scope for the roster PDF's coaches line."""
    title: str   # "Head Coach" / "Assistant Coach"
    first: str
    last: str


PERSONNEL_URL = "https://admin.esportsdesk.com/leagues/personnel.cfm"

_COACH_TITLES = {"head coach", "assistant coach"}
_COACH_ORDER = {"head coach": 0, "assistant coach": 1}


def fetch_team_html(team_id: int, client_id: int = 7132, league_id: int = 35501) -> str:
    """Download the stats_1team page HTML for `team_id`."""
    params = {"clientid": client_id, "leagueid": league_id, "teamid": team_id}
    url = f"{STATS_URL}?{urlencode(params)}"
    return fetch(url)


def fetch_personnel_html(team_id: int, client_id: int = 7132, league_id: int = 35501) -> str:
    """Download the personnel.cfm page HTML for `team_id` (coaching staff)."""
    params = {"clientid": client_id, "leagueid": league_id, "teamid": team_id}
    url = f"{PERSONNEL_URL}?{urlencode(params)}"
    return fetch(url)


def _split_first_last(full_name: str) -> tuple[str, str]:
    """Split 'Eli Seo Jun Paek' -> ('Eli Seo Jun', 'Paek').

    Hyphenated surnames stay whole ('Joel Keogh-Cope' -> ('Joel', 'Keogh-Cope')).
    Two-word surnames are detected from a small allowlist of particles.
    """
    parts = full_name.strip().split()
    if len(parts) == 1:
        return ("", parts[0])
    if len(parts) == 2:
        return (parts[0], parts[1])
    # Two-word surname allowlist — empty for now; add entries here as NZWIHL
    # multi-word surnames are flagged (mirrors NZIHL's approach).
    multi_word: set[str] = set()
    tail2 = " ".join(parts[-2:]).lower()
    if tail2 in multi_word:
        return (" ".join(parts[:-2]), " ".join(parts[-2:]))
    return (" ".join(parts[:-1]), parts[-1])


# Detect the table type by looking for either the SKATERS or GOALIES header.
_PLAYER_STATS_RE = re.compile(r"PLAYER STATISTICS[\s\S]*?TEAM TOTALS", re.IGNORECASE)
_GOALIE_STATS_RE = re.compile(r"GOALIE STATISTICS[\s\S]*?TEAM TOTALS", re.IGNORECASE)

# Match a table row, capturing the entire row HTML.
_TR_RE = re.compile(r"<tr[^>]*>([\s\S]*?)</tr>", re.IGNORECASE)
# Match each <td>'s text content.
_TD_RE = re.compile(r"<td[^>]*>([\s\S]*?)</td>", re.IGNORECASE)
# Quote-aware tag stripper. esportsdesk header cells wrap labels in
# `<span title="...">` tooltips, and some tooltip titles embed a literal
# `<br />` inside the quoted attribute value (e.g. GAA's "Goals Against
# Average<br />(based on a 60 minute game)"). A naive `<[^>]+>` stops at the
# first bare `>` it finds -- including one hiding inside a quoted attribute --
# which silently garbles the cleaned text and breaks header-label lookups.
# This pattern treats quoted substrings atomically so embedded `<`/`>` inside
# attribute values can't truncate the match early. (Ported from the NZIHL
# fix — same platform, same bug class. Mat, 2026-07-05)
_TAG_RE = re.compile(r'<(?:"[^"]*"|\'[^\']*\'|[^>"\'])*>')


def _clean(td_html: str) -> str:
    """Strip tags and decode entities."""
    return unescape(_TAG_RE.sub("", td_html)).strip()


def _row_flag(row_html: str) -> str:
    """Detect the trailing flag for a player row.

    Rendered after the second player link, e.g. `</a> IM`. We look for
    ` C` / ` A` / ` IM` / ` AF` / ` RO` at the end of the player-name cell
    (the first cell that contains an anchor).
    """
    for td in _TD_RE.findall(row_html):
        if "<a" in td:
            text = _clean(td)
            tail = text.split()[-1] if text else ""
            if tail in {"C", "A", "IM", "AF", "RO"}:
                return tail
            return ""
    return ""


def _player_full_name(row_html: str) -> str | None:
    """Pull the player's full name from the title="..." attribute."""
    m = _PLAYER_LINK.search(row_html)
    if not m:
        return None
    return m.group(2)


_TH_RE = re.compile(r"<th[^>]*>([\s\S]*?)</th>", re.IGNORECASE)


def _header_index_map(header_row_html: str) -> dict[str, int]:
    """{column label (cleaned, upper) -> cell index} from a <tr> of <th> cells."""
    return {_clean(th).upper(): i for i, th in enumerate(_TH_RE.findall(header_row_html))}


def parse_skaters(html: str, team_id: int) -> list[SkaterRow]:
    block = _PLAYER_STATS_RE.search(html)
    if not block:
        return []
    block_html = block.group(0)

    # Same platform as NZIHL: some stats_1team.cfm revisions insert a BY
    # birth-year column, or add PTS/+/- and other advanced columns. Read the
    # header row and locate each field by its label instead of a fixed
    # offset, so an extra/missing column upstream can't silently misalign
    # GP/G/A (or make +/- unreadable/absent).
    header_match = _TR_RE.search(block_html)
    col = _header_index_map(header_match.group(1)) if header_match else {}
    idx_num = col.get("#", 2)
    idx_pos = col.get("POSITION", 3)
    idx_gp  = col.get("GP", 4)
    idx_g   = col.get("G", 5)
    idx_a   = col.get("A", 6)
    idx_pm  = col.get("+/-")  # None on layouts that don't carry it

    rows: list[SkaterRow] = []
    for row_match in _TR_RE.finditer(block_html):
        row_html = row_match.group(1)
        full_name = _player_full_name(row_html)
        if not full_name:
            continue
        cells = [_clean(td) for td in _TD_RE.findall(row_html)]
        if len(cells) < max(idx_num, idx_pos, idx_gp, idx_g, idx_a) + 1:
            continue
        jersey = cells[idx_num] or "-"
        position = cells[idx_pos] or ""
        try:
            gp = int(cells[idx_gp]) if cells[idx_gp] not in ("", "-") else 0
            g = int(cells[idx_g]) if cells[idx_g] not in ("", "-") else 0
            a = int(cells[idx_a]) if cells[idx_a] not in ("", "-") else 0
        except ValueError:
            continue
        plus_minus = cells[idx_pm] if (idx_pm is not None and idx_pm < len(cells)) else ""
        first_raw, last_raw = _split_first_last(full_name)
        first, last = normalize_name(first_raw, last_raw, team_id, jersey)
        flag = _row_flag(row_html)
        rows.append(SkaterRow(
            jersey=jersey, last=last.upper() if last else "",
            first=first, position=position,
            gp=gp, g=g, a=a, flag=flag, plus_minus=plus_minus,
        ))
    return rows


def parse_goalies(html: str, team_id: int) -> list[GoalieRow]:
    block = _GOALIE_STATS_RE.search(html)
    if not block:
        return []
    block_html = block.group(0)

    # Same header-drift issue as parse_skaters: some stats_1team.cfm
    # revisions insert a BY (birth year) column between "#" and "GP" in the
    # GOALIE STATISTICS table too. Look up each field by header label instead
    # of a fixed offset so an extra column can't silently zero out GP (which
    # was making every goalie fall through to the bench as "hasn't played").
    header_match = _TR_RE.search(block_html)
    col = _header_index_map(header_match.group(1)) if header_match else {}
    idx_num    = col.get("#", 2)
    idx_gp     = col.get("GP", 3)
    idx_mp     = col.get("MP", 9)
    idx_gaa    = col.get("GAA", 11)
    idx_sv_pct = col.get("SV%", 15)

    rows: list[GoalieRow] = []
    for row_match in _TR_RE.finditer(block_html):
        row_html = row_match.group(1)
        full_name = _player_full_name(row_html)
        if not full_name:
            continue
        cells = [_clean(td) for td in _TD_RE.findall(row_html)]
        needed = max(idx_num, idx_gp, idx_mp, idx_gaa, idx_sv_pct) + 1
        if len(cells) < needed:
            continue
        jersey = cells[idx_num] or "-"
        try:
            gp = int(cells[idx_gp]) if cells[idx_gp] not in ("", "-") else 0
        except ValueError:
            gp = 0
        gaa = cells[idx_gaa] or "—"
        sv_pct = cells[idx_sv_pct] or "—"
        try:
            mp = int(cells[idx_mp]) if cells[idx_mp] not in ("", "-") else 0
        except ValueError:
            mp = 0
        first_raw, last_raw = _split_first_last(full_name)
        first, last = normalize_name(first_raw, last_raw, team_id, jersey)
        flag = _row_flag(row_html)
        rows.append(GoalieRow(
            jersey=jersey, last=last.upper() if last else "",
            first=first, gp=gp, gaa=gaa, sv_pct=sv_pct, flag=flag, mp=mp,
        ))
    return rows


def parse_coaches(html: str) -> list[CoachRow]:
    """Parse personnel.cfm's Title/Name table into Head Coach / Assistant
    Coach rows (see CoachRow). The Name cell holds first/last on separate
    lines within one <td> -- a literal newline in the source, not a <br> --
    so split on whitespace/newlines rather than looking for a tag."""
    rows: list[CoachRow] = []
    for row_match in _TR_RE.finditer(html):
        cells = [_clean(td) for td in _TD_RE.findall(row_match.group(1))]
        if len(cells) != 2:
            continue
        title = cells[0].strip()
        if title.lower() not in _COACH_TITLES:
            continue
        parts = [p.strip() for p in cells[1].split("\n") if p.strip()]
        if not parts:
            continue
        first, last = (parts[0], " ".join(parts[1:])) if len(parts) > 1 else ("", parts[0])
        rows.append(CoachRow(title=title, first=first, last=last))
    rows.sort(key=lambda r: _COACH_ORDER.get(r.title.lower(), 2))
    return rows


def scrape_team(team_id: int, html: str | None = None) -> tuple[list[SkaterRow], list[GoalieRow]]:
    """Scrape a team's roster. Pass `html` to bypass the network (testing)."""
    if html is None:
        html = fetch_team_html(team_id)
    return parse_skaters(html, team_id), parse_goalies(html, team_id)
