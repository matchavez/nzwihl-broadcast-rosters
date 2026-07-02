"""Tests for expand_to_series: a series found in the lookahead window should
pull in the rest of its games even when they fall outside the window.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nzwihl_rosters.schedule import Game, expand_to_series, group_into_series
from nzwihl_rosters.teams import TEAMS

NZ_TZ = ZoneInfo("Pacific/Auckland")

STEEL = TEAMS["AUCKLAND STEEL"]
INFERNO = TEAMS["CANTERBURY INFERNO"]
DTW = TEAMS["DUNEDIN THUNDER WOMEN"]
WILD = TEAMS["WAKATIPU WILD"]


def _dt(y, m, d, h=19, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=NZ_TZ)


def _g(dt, away, home, is_final=False, **kw):
    return Game(dt, away=away, home=home, venue=home.home_venue, is_final=is_final, **kw)


def test_sunday_game_pulled_in_when_saturday_is_in_window():
    sat = _g(_dt(2026, 7, 4, 19, 0), STEEL, INFERNO)
    sun = _g(_dt(2026, 7, 5, 15, 0), STEEL, INFERNO)
    all_games = [sat, sun]

    window_games = [sat]
    expanded = expand_to_series(window_games, all_games)

    assert len(expanded) == 2
    assert sat in expanded and sun in expanded
    assert expanded == sorted(expanded, key=lambda g: g.start_local)


def test_unrelated_series_not_pulled_in():
    sat = _g(_dt(2026, 7, 4, 19, 0), STEEL, INFERNO)
    sun = _g(_dt(2026, 7, 5, 15, 0), STEEL, INFERNO)
    other = _g(_dt(2026, 7, 6, 18, 0), DTW, WILD)
    all_games = [sat, sun, other]

    window_games = [sat]
    expanded = expand_to_series(window_games, all_games)

    assert other not in expanded
    assert len(expanded) == 2


def test_rematch_more_than_3_days_later_not_pulled_in():
    sat = _g(_dt(2026, 7, 4, 19, 0), STEEL, INFERNO)
    later = _g(_dt(2026, 7, 18, 19, 0), STEEL, INFERNO)
    all_games = [sat, later]

    window_games = [sat]
    expanded = expand_to_series(window_games, all_games)

    assert later not in expanded
    assert expanded == [sat]


def test_final_games_excluded_from_expansion():
    sat = _g(_dt(2026, 7, 4, 19, 0), STEEL, INFERNO, is_final=True, away_score=3, home_score=2)
    sun = _g(_dt(2026, 7, 5, 15, 0), STEEL, INFERNO)
    all_games = [sat, sun]

    window_games = [sun]
    expanded = expand_to_series(window_games, all_games)

    assert expanded == [sun]


def test_empty_window_returns_empty():
    assert expand_to_series([], [_g(_dt(2026, 7, 4), STEEL, INFERNO)]) == []


def test_expanded_games_still_group_into_one_series_for_pdf():
    sat = _g(_dt(2026, 7, 4, 19, 0), STEEL, INFERNO)
    sun = _g(_dt(2026, 7, 5, 15, 0), STEEL, INFERNO)
    expanded = expand_to_series([sat], [sat, sun])
    series = group_into_series(expanded)
    assert len(series) == 1
    assert series[0] == [sat, sun]
