"""CLI entrypoint.

Usage:
    python -m nzwihl_rosters --within-days 4 --output ./output
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .layout import build_roster_pdf, GameInfo
from .schedule import upcoming_within, group_into_series, expand_to_series, Game, fetch_schedule_html, parse_schedule
from . import boxscores
from .scraper import scrape_team, fetch_personnel_html, parse_coaches


def _round_label(start: datetime) -> str:
    opener = datetime(start.year, 5, 8, tzinfo=start.tzinfo)
    weeks = max(0, (start.date() - opener.date()).days // 7)
    return f"Rd {weeks+1:02d}"


def _date_label(series: list[Game]) -> str:
    parts = []
    for g in series:
        parts.append(g.start_local.strftime("%a %d %b %H:%M"))
    return " & ".join(parts)


def _filename(series: list[Game]) -> str:
    first = series[0]
    return f"{first.start_local.strftime('%Y-%m-%d')}_{first.away.short_code}_at_{first.home.short_code}.pdf"


def _fetch_coaches(team_id: int) -> list:
    """Best-effort coaching-staff lookup. personnel.cfm is a separate page
    from stats_1team.cfm -- if it's ever down, slow, or reshaped, a roster
    PDF should still build with everything except the coaches line rather
    than fail outright (same philosophy as boxscores.py's manifest writer)."""
    try:
        return parse_coaches(fetch_personnel_html(team_id))
    except Exception:
        return []


def build_series_pdf(series: list[Game], output_dir: Path) -> Path:
    first = series[0]
    away_skaters, away_goalies = scrape_team(first.away.team_id)
    home_skaters, home_goalies = scrape_team(first.home.team_id)
    away_coaches = _fetch_coaches(first.away.team_id)
    home_coaches = _fetch_coaches(first.home.team_id)
    info = GameInfo(
        round_label=_round_label(first.start_local),
        date_label=_date_label(series),
        venue=first.venue,
    )
    out_path = output_dir / _filename(series)
    return Path(build_roster_pdf(
        out_path=str(out_path),
        away_team=first.away, away_skaters=away_skaters, away_goalies=away_goalies,
        home_team=first.home, home_skaters=home_skaters, home_goalies=home_goalies,
        game_info=info,
        away_coaches=away_coaches, home_coaches=home_coaches,
    ))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build NZWIHL roster PDFs for upcoming games.")
    p.add_argument("--within-days", type=int, default=4,
                   help="Generate PDFs only for games starting within this many days (default 4).")
    p.add_argument("--manifest-within-days", type=int, default=11,
                   help="Include games in boxscores.json up to this many days out (default 11), "
                        "even before a PDF is generated for them. Lets the hockeyrosters page show "
                        "'coming soon' cards further ahead than the portal, without changing which "
                        "games get PDFs (--within-days) or how far ahead the portal displays.")
    p.add_argument("--output", type=Path, default=Path("output"),
                   help="Directory for generated PDFs.")
    p.add_argument("--dry-run", action="store_true",
                   help="List upcoming games without generating PDFs.")
    args = p.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)

    schedule_html = fetch_schedule_html()
    window_games = upcoming_within(args.within_days, html=schedule_html)
    # A series (same two teams, <=3 days apart) can straddle the window
    # cutoff — e.g. a Wednesday sweep catches Saturday's game but the window
    # ends before Sunday's. Pull in the rest of any series we've already
    # found the start of, even if it falls outside --within-days.
    all_games = parse_schedule(schedule_html)
    games = expand_to_series(window_games, all_games)

    # Wider lookahead used only for boxscores.json (not PDF generation) — lets
    # the hockeyrosters page list games further out as "coming soon" while the
    # portal and PDF pipeline keep behaving exactly as before (see core_keys).
    manifest_window_games = upcoming_within(args.manifest_within_days, html=schedule_html)
    manifest_games = expand_to_series(manifest_window_games, all_games)
    core_keys = {(g.away.team_id, g.home.team_id, g.start_local) for g in games}

    # NOTE: we deliberately do NOT early-return when `games` is empty. A run
    # with nothing upcoming still needs to write boxscores.json so it can prune
    # entries that have aged out — otherwise a stale card (e.g. last week's
    # game, with nothing yet scheduled to replace it) sits on the portal
    # forever, since no later run would ever touch the file again.
    series = group_into_series(games) if games else []
    if games:
        print(f"Found {len(games)} upcoming game(s) in {len(series)} series:")
        for s in series:
            first = s[0]
            print(f"  • {first.away.short_code} at {first.home.short_code} — "
                  f"{_date_label(s)} — {first.venue}")
    else:
        print(f"No upcoming games within {args.within_days} days.")
    print(f"    (manifest lookahead: {len(manifest_games)} game(s) within "
          f"{args.manifest_within_days} days)")

    if args.dry_run:
        return 0

    for s in series:
        try:
            out = build_series_pdf(s, args.output)
            print(f"    → wrote {out.name}")
        except Exception as exc:
            print(f"    ! failed: {exc}", file=sys.stderr)

    try:
        manifest = boxscores.write_manifest(
            args.output / "boxscores.json", manifest_games, schedule_html,
            existing_path=Path("boxscores.json"),  # the repo-root committed manifest
            core_keys=core_keys,
        )
        n_ok = sum(1 for g in manifest["games"] if g["gameid"])
        print(f"    → wrote boxscores.json ({n_ok}/{len(manifest['games'])} entries, "
              f"{n_ok} gameids resolved, stale entries >{boxscores.DEFAULT_KEEP_DAYS}d pruned)")
    except Exception as exc:  # noqa: BLE001 — best-effort, never abort the run
        print(f"    ! boxscores manifest failed: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
