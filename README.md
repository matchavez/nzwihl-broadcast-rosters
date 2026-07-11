# nzwihl-broadcast-rosters

Auto-generated single-page roster PDFs for the NZWIHL broadcast booth. Pulls live rosters and the upcoming schedule from esportsdesk, applies a few name corrections the league hasn't fixed yet, and renders one PDF per upcoming series. This is the NZWIHL sibling of [matchavez/nzihl-broadcast-rosters](https://github.com/matchavez/nzihl-broadcast-rosters) — same pipeline, women's league.

Runs daily on GitHub Actions; PDFs land as a release artifact attached to the run, and a `boxscores.json` manifest is committed for downstream pages (see `matchavez/hockeyrosters`).

## What it produces

For each upcoming series within the next 4 days, one A4 portrait PDF:

- Two columns, away team on the left, home team on the right.
- Centred team-name header in the team's primary colour.
- A compact `HC <name>   AC <name>, <name>` coaching-staff line under each
  team's header band, scraped from `personnel.cfm`. No line is drawn if a
  team has no Head/Assistant Coach listed — the lookup is best-effort and
  never fails the whole PDF.
- Goalie cards across the top (GP > 0 only) with `GP / GAA / SV%`.
- Skaters sorted by jersey #, with `POS  G  A` columns.
- Top-3 scorers per team (by G+A) get a pale honey row highlight.
- Players who haven't dressed yet — including goalies — fall into a dimmed "NOT YET PLAYED THIS SEASON" group at the bottom of each column.

`boxscores.json` also lists games up to **11 days** out (no PDF yet), separate from the 4-day PDF window, so `hockeyrosters` can show them further ahead as "coming soon."

## Project layout

```
src/nzwihl_rosters/
  teams.py         # registry: team_id, display name, colours, home venue
  overrides.py     # explicit name overrides + title-casing
  scraper.py       # parses stats team pages + personnel.cfm into Skater/Goalie/CoachRow lists
  schedule.py      # parses the schedule into a list of upcoming Games
  layout.py        # the single-page PDF builder
  cli.py           # CLI: schedule → filter window → group → render
.github/workflows/build-rosters.yml   # daily cron (17:30 UTC), publishes release + boxscores.json
tests/             # unit tests against hand-crafted HTML fixtures
```

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

# What would run today?
python -m nzwihl_rosters --within-days 4 --dry-run

# Actually render the PDFs into ./output/
python -m nzwihl_rosters --within-days 4 --manifest-within-days 11 --output ./output
```

Trigger a run manually any time:

```bash
gh workflow run "Build rosters"
```

## Adding a player-name override

Edit `src/nzwihl_rosters/overrides.py`:

```python
SURNAME_OVERRIDES = {
    # (team_id, jersey_number): (correct_surname, correct_first_or_None)
}
```

The override is keyed by `(team_id, jersey)` so it survives even if the league's own records are wrong. Lowercase-stored names (e.g. `harry louw`) are auto-title-cased by `normalize_name`, so you only need explicit entries for names that need a *non-trivial* correction.

## Adding / updating a team

Edit `src/nzwihl_rosters/teams.py`. Colours come from the **2026 NZIHL/NZWIHL Style Guide** in the `nzihl-broadcast-assets` repo. Venue names must match the canonical list (Paradice Avondale/Botany, Alpine Ice Centre, Dunedin Ice Stadium, Queenstown Ice Arena) — scraped venue text is normalized against it.

## Testing

```bash
PYTHONPATH=src python -m pytest tests/
```

Fixture-based tests don't hit the network. CI also runs the live fetch as part of every build, so upstream HTML drift surfaces as a workflow failure.

## Notes

- Scraping goes through the no-cache `admin.esportsdesk.com` origin (not the cached public site).
- `boxscores.json` self-prunes entries more than 3 days past their date.
