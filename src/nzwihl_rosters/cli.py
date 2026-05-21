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
from .schedule import upcoming_within, group_into_series, Game
from .scraper import scrape_team


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


def build_series_pdf(series: list[Game], output_dir: Path) -> Path:
    first = series[0]
    away_skaters, away_goalies = scrape_team(first.away.team_id)
    home_skaters, home_goalies = scrape_team(first.home.team_id)
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
    ))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build NZWIHL roster PDFs for upcoming games.")
    p.add_argument("--within-days", type=int, default=4,
                   help="Generate PDFs only for games starting within this many days (default 4).")
    p.add_argument("--output", type=Path, default=Path("output"),
                   help="Directory for generated PDFs.")
    p.add_argument("--dry-run", action="store_true",
                   help="List upcoming games without generating PDFs.")
    args = p.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)

    games = upcoming_within(args.within_days)
    if not games:
        print(f"No upcoming games within {args.within_days} days.")
        return 0

    series = group_into_series(games)
    print(f"Found {len(games)} upcoming game(s) in {len(series)} series:")
    for s in series:
        first = s[0]
        print(f"  • {first.away.short_code} at {first.home.short_code} — "
              f"{_date_label(s)} — {first.venue}")

    if args.dry_run:
        return 0

    for s in series:
        try:
            out = build_series_pdf(s, args.output)
            print(f"    → wrote {out.name}")
        except Exception as exc:
            print(f"    ! failed: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
