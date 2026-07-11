# memory.md — matchavez/nzwihl-broadcast-rosters

Self-context for Claude. README.md now exists (added 2026-07-11), modeled on the NZIHL sibling's README with corrected current-state details (cron, NZWIHL support, no-cache origin). This repo is the NZWIHL sibling of matchavez/nzihl-broadcast-rosters; same architecture (`src/nzwihl_rosters/{teams,overrides,scraper,schedule,layout,cli}.py`, `tests/`, `boxscores.json` manifest), just the women's league. Last refreshed: 2026-07-11 (coaching-staff line added).

## Automation
- Cron `30 17 * * *` UTC. Workflow comment was fixed 2026-07-11 (used to say "19:00 UTC", now correctly says 17:30 UTC, matching the NZIHL sibling fix).
- PDF window 4 days, manifest lookahead 11 days, same decoupling rationale as nzihl-broadcast-rosters.
- `contents: write` permission for `boxscores.json` commits + release publishing.

## Coaching staff line (2026-07-11)
Ported from the NZIHL sibling (its commit 118451f) the same day: a compact
`HC <name>   AC <name>, <name>` strip under each team's header band, sourced
from `personnel.cfm` (`admin.esportsdesk.com/leagues/personnel.cfm?clientid=7132&leagueid=35501&teamid=<id>`
— same platform/endpoint shape as NZIHL, different client/league IDs, same
as `fetch_team_html`'s existing defaults). Only Head Coach/Assistant Coach
rows are kept out of the Title/Name table (`CoachRow`/`parse_coaches`/
`fetch_personnel_html` in `scraper.py`). Design (one line, no section
header, HC/AC short labels, auto-shrink + ellipsis-truncate safety net) was
locked in on the NZIHL side first after a round of Mat's feedback — see that
repo's memory.md for the full back-story — then ported here verbatim.
`cli.py`'s coach lookup is best-effort (`try/except -> []`); `build_roster_pdf`'s
`away_coaches`/`home_coaches` kwargs default `None`, so it's additive, not
breaking.

## stats.json export (2026-07-12)
Ported from the NZIHL sibling verbatim: `src/nzwihl_rosters/stats_export.py`,
wired into `cli.py` as a best-effort step after the boxscores manifest write.
Emits `stats.json` at repo root (`{"generated_at","league":"nzwihl","teams":{"<TLA>":{...}}}`),
same shape and same header-label column-lookup robustness as NZIHL (skaters
now carry `pim`; goalies carry `ga`/`so`/`w`/`l`). `build-rosters.yml` commits
it with content-diffing so an unchanged day produces no commit.

**Why it exists:** feeds the new **Player Lower Thirds** control page in
`matchavez/hockey` (`hockey/lowerthirds/` + `activity-banner/`) -- this repo
and its NZIHL sibling are the sole source of season stat totals for that
project. See Claude's `nzihl-player-lower-thirds` memory for the full design.

## Known gotchas fixed here
- **Month-boundary `last_final_gameid` bug (2026-07-08):** this is where the bug was *first* found (NZWIHL/Inferno hit 0/4 gameids resolved when the last Final fell in the prior calendar month) — root cause fixed here, then pre-emptively ported to the NZIHL sibling.
- **Venue normalization (2026-07-01):** scraped schedule venue text is normalized to the canonical venue list (Paradice Avondale/Botany, Alpine Ice Centre, Dunedin Ice Stadium, Queenstown Ice Arena); `Team.home_venue` fallbacks fixed at the same time.
- **Scrape origin (2026-06-30):** switched schedule/stats/box-score scraping to the no-cache `admin.esportsdesk.com` origin (matches the switch made across the whole family of hockey repos).
- **`boxscores.json` self-pruning (2026-07-02):** drops entries more than 3 days past their date so the manifest doesn't grow unbounded.
- 2026-07-04: brought roster PDFs to visual parity with NZIHL (header-driven scraper, house font, goalie cap).

## Related repos
- **matchavez/nzihl-broadcast-rosters** — the men's-league twin; fixes should generally land on one then get ported to the other (check both when debugging a shared-code-path issue).
- **matchavez/hockeyrosters** — consumes this repo's release PDFs + `boxscores.json`.
- **matchavez/nzihl-season-data** — separate, covers *completed* box scores across both leagues; this repo only cares about upcoming games.

## Sync note
Keep this file (and a README.md, if one gets added) in sync with every meaningful change. If they drift, flag it to Mat and get approval before publishing the sync rather than doing it silently.
