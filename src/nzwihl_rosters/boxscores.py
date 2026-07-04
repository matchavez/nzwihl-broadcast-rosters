"""Resolve box-score gameids for upcoming games → JSON manifest.

esportsdesk assigns sequential gameids when the season schedule is created, but
the public schedule only surfaces a game's `hockey_boxscores.cfm` link once the
game is **Final**. For *upcoming* games we therefore have to discover the
gameid ourselves. We do it by:

  1. Reading the highest gameid already linked on the schedule (= last played).
  2. Probing the next box-score "shells" (`hockey_boxscores.cfm?...&printPage=1`),
     which already carry the two teamIDs + date before the game is played.
  3. Matching each shell to an upcoming Game by (date, {away_id, home_id}).

This piggy-backs on the schedule HTML the roster build already fetches, so the
schedule is only downloaded once per run.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import date as _date, timedelta
from urllib.parse import urlencode

from .http import fetch
from .schedule import Game, fetch_schedule_html, upcoming_within

LEAGUE = "NZWIHL"
CLIENT_ID = 7132
LEAGUE_ID = 35501
BOXSCORE_URL = "https://admin.esportsdesk.com/leagues/hockey_boxscores.cfm"

# Any boxscore link on the schedule (only present for played games).
_SCHED_GAMEID_RE = re.compile(r"hockey_boxscores\.cfm\?[^\"'<> ]*gameid=(\d+)", re.IGNORECASE)
# stats_1team links carry the teamID — in a printPage shell only the two game
# teams appear (away first, home second).
_TEAMID_RE = re.compile(r"stats_1team\.cfm\?[^\"'<> ]*teamID=(\d+)", re.IGNORECASE)
# "June 27th, 2026" — month name first, optional ordinal suffix.
_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?,\s*(\d{4})",
    re.IGNORECASE,
)
_MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"]
)}


def public_boxscore_url(gameid: int, client_id: int = CLIENT_ID, league_id: int = LEAGUE_ID) -> str:
    return f"{BOXSCORE_URL}?{urlencode({'clientid': client_id, 'leagueid': league_id, 'gameid': gameid})}"


def _shell_url(gameid: int, client_id: int = CLIENT_ID, league_id: int = LEAGUE_ID) -> str:
    return f"{BOXSCORE_URL}?{urlencode({'clientid': client_id, 'leagueid': league_id, 'gameid': gameid, 'printPage': 1})}"


def last_final_gameid(schedule_html: str) -> int | None:
    ids = [int(m.group(1)) for m in _SCHED_GAMEID_RE.finditer(schedule_html)]
    return max(ids) if ids else None


def parse_shell(html: str) -> dict | None:
    """Pull {away_id, home_id, date} from a printPage box-score shell.

    Returns None if the page doesn't look like a real game shell.
    """
    team_ids: list[int] = []
    for m in _TEAMID_RE.finditer(html):
        tid = int(m.group(1))
        if tid not in team_ids:
            team_ids.append(tid)
    if len(team_ids) < 2:
        return None
    dm = _DATE_RE.search(html)
    if not dm:
        return None
    d = _date(int(dm.group(3)), _MONTHS[dm.group(1).lower()], int(dm.group(2)))
    return {"away_id": team_ids[0], "home_id": team_ids[1], "date": d}


def _probe_shells(start_gameid: int, probe_ahead: int,
                  client_id: int, league_id: int) -> dict[int, dict]:
    shells: dict[int, dict] = {}
    for gid in range(start_gameid + 1, start_gameid + 1 + probe_ahead):
        try:
            parsed = parse_shell(fetch(_shell_url(gid, client_id, league_id)))
        except Exception:  # noqa: BLE001 — best-effort; skip unreachable ids
            parsed = None
        if parsed:
            shells[gid] = parsed
    return shells


def resolve(games: list[Game], schedule_html: str, *,
            client_id: int = CLIENT_ID, league_id: int = LEAGUE_ID,
            probe_ahead: int = 12, core_keys: set[tuple] | None = None) -> list[dict]:
    """Map each upcoming Game to its gameid (or None if it can't be resolved).

    If `core_keys` is given, each returned dict gets an `in_core_window` flag —
    True if the game is inside the narrower PDF-generation window, False if it
    only qualified for the wider manifest-only lookahead (used by the
    hockeyrosters page to show 'coming soon' cards further out than the
    portal). If `core_keys` is None, every game is marked in_core_window=True
    (back-compat: single-window callers/tests).
    """
    last = last_final_gameid(schedule_html)
    shells = _probe_shells(last, probe_ahead, client_id, league_id) if last else {}
    used: set[int] = set()
    out: list[dict] = []
    for g in games:
        gdate = g.start_local.date()
        key = (g.away.team_id, g.home.team_id, g.start_local)
        in_core = True if core_keys is None else key in core_keys
        match_id = None
        for gid, p in shells.items():
            if gid in used:
                continue
            if p["date"] == gdate and {p["away_id"], p["home_id"]} == {g.away.team_id, g.home.team_id}:
                match_id = gid
                break
        if match_id:
            used.add(match_id)
        out.append({
            "date": g.start_local.strftime("%Y-%m-%d"),
            "time": g.start_local.strftime("%I:%M %p").lstrip("0"),
            "datetime": g.start_local.isoformat(),
            "away": g.away.display_name,
            "away_code": g.away.short_code,
            "home": g.home.display_name,
            "home_code": g.home.short_code,
            "venue": g.venue,
            "gameid": match_id,
            "boxscore_url": public_boxscore_url(match_id, client_id, league_id) if match_id else None,
            "in_core_window": in_core,
        })
    return out


# How long a played (or otherwise no-longer-upcoming) game's card stays on the
# portal after its date before it's pruned from the manifest. A fresh run that
# finds zero upcoming games would otherwise never touch the file again and a
# stale card (e.g. last week's NZWIHL game) would sit there indefinitely — see
# the roster-schedule-pipeline project notes.
DEFAULT_KEEP_DAYS = 3


def _parse_iso_date(s: str) -> _date:
    y, m, d = (int(x) for x in s.split("-"))
    return _date(y, m, d)


def prune_and_merge(existing_games: list[dict], new_games: list[dict], *,
                     keep_days: int = DEFAULT_KEEP_DAYS,
                     today: _date | None = None) -> list[dict]:
    """Merge freshly-resolved upcoming games onto the previous manifest.

    Old entries are kept for `keep_days` past their date (so a just-played
    game's box-score card doesn't vanish the instant it's over) and dropped
    after that unless a new run has already replaced them. This makes the
    manifest self-cleaning even on runs that find zero upcoming games, instead
    of relying on every run finding a replacement to overwrite stale data.
    """
    today = today or _date.today()
    cutoff = today - timedelta(days=keep_days)
    new_keys = {(g["date"], g["away"], g["home"]) for g in new_games}
    kept_old = [
        g for g in existing_games
        if _parse_iso_date(g["date"]) >= cutoff
        and (g["date"], g["away"], g["home"]) not in new_keys
    ]
    merged = kept_old + new_games
    merged.sort(key=lambda g: g["datetime"])
    return merged


def build_manifest(games: list[Game], schedule_html: str, *,
                    existing_games: list[dict] | None = None,
                    keep_days: int = DEFAULT_KEEP_DAYS,
                    core_keys: set[tuple] | None = None) -> dict:
    games = sorted(games, key=lambda g: g.start_local)
    new_resolved = resolve(games, schedule_html, core_keys=core_keys)
    merged = prune_and_merge(existing_games or [], new_resolved, keep_days=keep_days)
    return {"league": LEAGUE, "games": merged}


def write_manifest(out_path, games: list[Game], schedule_html: str | None = None, *,
                    existing_path=None, keep_days: int = DEFAULT_KEEP_DAYS,
                    core_keys: set[tuple] | None = None) -> dict:
    """Write the manifest to `out_path`, merging against the manifest already
    committed at `existing_path` (defaults to `out_path` itself if not given —
    pass the repo-root boxscores.json explicitly when `out_path` is a fresh
    build-output directory that won't yet contain the previous run's file).
    """
    if schedule_html is None:
        schedule_html = fetch_schedule_html()
    existing_path = Path(existing_path) if existing_path is not None else Path(out_path)
    existing_games: list[dict] = []
    if existing_path.exists():
        try:
            existing_games = json.loads(existing_path.read_text()).get("games", [])
        except Exception:  # noqa: BLE001 — corrupt/missing file: start fresh, don't abort
            existing_games = []
    manifest = build_manifest(games, schedule_html, existing_games=existing_games,
                               keep_days=keep_days, core_keys=core_keys)
    Path(out_path).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
