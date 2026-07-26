"""Emit a machine-readable stats.json snapshot for the whole NZWIHL registry.

Ported from the NZIHL sibling repo's stats_export.py (same platform, same
parsers, just NZWIHL's client_id/league_id, 4-team registry, and nzwihl.json
warehouse file). See that repo's version for the full rationale comment.

Skater G/A/PTS source (2026-07-13): season totals for skaters are sourced
from matchavez/nzihl-season-data's committed warehouse (nzwihl.json's
`derived.player_game_logs`) instead of stats_1team.cfm's own G/A/PTS
columns, verified byte-for-byte against every skater on all 4 NZWIHL teams
(including the Canterbury Inferno parenthetical-maiden-name cases). Every
other skater field (jersey, position, flag, GP, PIM), and every goalie/coach
field, is still scraped from stats_1team.cfm/personnel.cfm directly --
PIM and goalie stats were verified NOT to be safely reproducible from the
warehouse and were deliberately left alone (see this repo's memory.md).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .teams import TEAMS, Team
from .scraper import (
    scrape_team,
    fetch_personnel_html,
    parse_coaches,
)
from .http import fetch

# matchavez/nzihl-season-data's committed warehouse -- see that repo's
# README for the full schema. We only need `derived.player_game_logs`.
_SEASON_DATA_URL = "https://raw.githubusercontent.com/matchavez/nzihl-season-data/main/nzwihl.json"


def _normalize_name(name: str) -> str:
    """Lowercase, alpha-only. MUST mirror nzihl-season-data's own
    `parser.normalize_name()` exactly -- this is the key player_game_logs is
    keyed by, so any drift here silently breaks every lookup."""
    return re.sub(r"[^a-z]", "", (name or "").lower())


def fetch_player_game_logs() -> dict:
    """Best-effort fetch of the season-data warehouse's player_game_logs.
    Returns {} on ANY failure (network hiccup, file missing, shape change)
    so a warehouse outage degrades gracefully to the original
    stats_1team.cfm-scraped G/A/PTS rather than failing the whole export."""
    try:
        raw = fetch(_SEASON_DATA_URL)
        data = json.loads(raw)
        return data.get("derived", {}).get("player_game_logs", {}) or {}
    except Exception as exc:  # noqa: BLE001 — best-effort, see docstring
        print(f"    ! stats.json: nzihl-season-data fetch failed: {exc}")
        return {}


def _warehouse_goals_assists(raw_name: str, game_logs: dict) -> tuple[int, int] | None:
    """Look up a skater's season (goals, assists) from the warehouse by their
    RAW scraped name (title="..." text, before any split/override
    correction). This is deliberate: nzihl-season-data's box-score parser
    preserves a player's display name verbatim in `goals[].who`/`assists[]`,
    parenthetical maiden-name/nickname text and all (e.g. "Reagyn Shattock
    (Niskakoski)", "Lucy-Jane(LJ) Hart"), so normalizing the UN-overridden
    raw name is what actually matches its key -- normalizing the
    override-corrected first/last (e.g. "Reagyn Shattock") would silently
    miss.

    Returns None if the player has no warehouse entry at all (0 G/0 A this
    season is the overwhelmingly common reason -- a player with zero
    recorded goals or assists never gets a player_game_logs key). The
    caller treats None as "keep the scraped value," which is safe either
    way since the scraped value would also read 0/0 for that player.
    """
    entry = game_logs.get(_normalize_name(raw_name))
    if entry is None:
        return None
    g = sum(gl["goals"] for gl in entry["games"])
    a = sum(gl["assists"] for gl in entry["games"])
    return g, a


def _skater_dict(row, game_logs: dict) -> dict:
    g, a = row.g, row.a
    warehouse = _warehouse_goals_assists(row.raw_name or f"{row.first} {row.last}", game_logs)
    if warehouse is not None:
        g, a = warehouse
    return {
        "number": row.jersey,
        "first": row.first,
        "last": row.last,
        "position": row.position,
        "flag": row.flag,
        "gp": row.gp,
        "g": g,
        "a": a,
        "pts": g + a,
        "pim": row.pim,
        "player_id": row.player_id,
    }


def _goalie_dict(row) -> dict:
    return {
        "number": row.jersey,
        "first": row.first,
        "last": row.last,
        "flag": row.flag,
        "gp": row.gp,
        "min": row.mp,
        "ga": row.ga,
        "gaa": row.gaa,
        "sv_pct": row.sv_pct,
        "so": row.so,
        "w": row.w,
        "l": row.l,
        "player_id": row.player_id,
    }


def _coach_dict(row) -> dict:
    return {"title": row.title, "first": row.first, "last": row.last}


def scrape_team_stats(team: Team, client_id: int, league_id: int, game_logs: dict) -> dict:
    """Scrape one team's skaters/goalies/coaches into stats.json's per-team shape."""
    skaters, goalies = scrape_team(team.team_id)
    try:
        coaches = parse_coaches(fetch_personnel_html(team.team_id, client_id, league_id))
    except Exception:
        coaches = []
    return {
        "team_id": team.team_id,
        "display_name": team.display_name,
        "skaters": [_skater_dict(r, game_logs) for r in skaters],
        "goalies": [_goalie_dict(r) for r in goalies],
        "coaches": [_coach_dict(r) for r in coaches],
    }


def scrape_all_teams_stats(client_id: int = 7132, league_id: int = 35501) -> dict[str, dict]:
    """Scrape every registered team. Best-effort per team — a failure for one
    team logs and is skipped rather than aborting the whole export."""
    try:
        game_logs = fetch_player_game_logs()
    except Exception as exc:  # noqa: BLE001 — belt-and-suspenders: fetch_player_game_logs()
        # already catches network/shape errors internally and returns {}, but
        # this call site degrades the same way for anything that slips past
        # that, since a warehouse hiccup must never sink the whole export.
        print(f"    ! stats.json: nzihl-season-data fetch failed: {exc}")
        game_logs = {}
    out: dict[str, dict] = {}
    for team in TEAMS.values():
        try:
            out[team.short_code] = scrape_team_stats(team, client_id, league_id, game_logs)
        except Exception as exc:  # noqa: BLE001 — best-effort, one team can't sink the run
            print(f"    ! stats.json: {team.short_code} scrape failed: {exc}")
    return out


def write_stats_json(
    out_path: Path,
    league_key: str,
    client_id: int = 7132,
    league_id: int = 35501,
    teams_stats: dict[str, dict] | None = None,
) -> dict:
    """Scrape (unless `teams_stats` is pre-supplied, e.g. by a test) and write
    stats.json. Returns the written payload dict."""
    if teams_stats is None:
        teams_stats = scrape_all_teams_stats(client_id, league_id)
    payload = {
        "generated_at": date.today().isoformat(),
        "league": league_key,
        "teams": teams_stats,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload
