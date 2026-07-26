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

## Skater G/A/PTS now sourced from nzihl-season-data (2026-07-13)
Ported from the NZIHL sibling verbatim (same day): `stats_export.py` sources
skater goals/assists/points from `matchavez/nzihl-season-data`'s committed
`nzwihl.json` (`derived.player_game_logs`) instead of `stats_1team.cfm`'s
own G/A/PTS columns, falling back to the scraped value on any miss (no
warehouse entry) or fetch failure (best-effort, same as the coaches fetch).
`stats_1team.cfm` is still scraped for jersey/position/flag/GP/PIM and for
every goalie/coach field -- GP in particular can't come from the warehouse
(`player_game_logs` only has scoring games, not every game dressed).

**Matching key is the RAW pre-override scraped name**, not the
override-corrected display name -- `SkaterRow` grew a `raw_name` field
(the exact `title="..."` text) because nzihl-season-data's parser stores
names verbatim, parenthetical text and all. This repo's OWN Canterbury
Inferno players are the exact case that proves it necessary: **#3 Reagyn
Shattock** is stored as `"Reagyn Shattock (Niskakoski)"` in the warehouse
(her maiden name, kept raw) but as `"Reagyn Shattock"` after this repo's
own `SURNAME_OVERRIDES` correction -- normalizing the corrected name would
silently miss her warehouse entry. `_normalize_name()` here (lowercase,
alpha-only) intentionally mirrors nzihl-season-data's own
`parser.normalize_name()` exactly.

**Verification (2026-07-13, before shipping):** every skater on all 9
NZIHL+NZWIHL teams checked against a live, cache-busted `stats_1team.cfm`
fetch (use `stats_1teamV2.cfm`, not the `printPage=1` view, which can
serve a stale snapshot up to ~2 weeks old on a low-traffic team page) --
G/A/PTS matched exactly everywhere, INCLUDING Reagyn Shattock and
Canterbury Inferno's other tricky name (#94 Lucy-Jane(LJ) Hart).

**PIM and all goalie fields were evaluated and deliberately NOT
migrated** -- real, unexplained mismatches turned up in live verification
(a suspension-affected major+misconduct PIM combo on the NZIHL side, plus
split-goalie no-decision games with no way to tell which goalie gets
credit from `games[].goalies[]` alone). Full evidence in the NZIHL
sibling's memory.md -- same warehouse, same finding, applies to both
leagues equally.

## Known gotchas fixed here
- **Month-boundary `last_final_gameid` bug (2026-07-08):** this is where the bug was *first* found (NZWIHL/Inferno hit 0/4 gameids resolved when the last Final fell in the prior calendar month) — root cause fixed here, then pre-emptively ported to the NZIHL sibling.
- **Venue normalization (2026-07-01):** scraped schedule venue text is normalized to the canonical venue list (Paradice Avondale/Botany, Alpine Ice Centre, Dunedin Ice Stadium, Queenstown Ice Arena); `Team.home_venue` fallbacks fixed at the same time.
- **Scrape origin (2026-06-30):** switched schedule/stats/box-score scraping to the no-cache `admin.esportsdesk.com` origin (matches the switch made across the whole family of hockey repos).
- **`boxscores.json` self-pruning (2026-07-02):** drops entries more than 3 days past their date so the manifest doesn't grow unbounded.
- 2026-07-04: brought roster PDFs to visual parity with NZIHL (header-driven scraper, house font, goalie cap).

## 2026-07-27: player_id added to stats.json
Same fix as the NZIHL sibling, ported across: SkaterRow/GoalieRow and stats.json now carry
`player_id`. See that repo's memory.md for the full rationale (built for the new
pronunciation-guide system in matchavez/nzihl-broadcast-assets). Verified live via
workflow_dispatch -- player_id populated for all 4 teams.

## Related repos
- **matchavez/nzihl-broadcast-rosters** — the men's-league twin; fixes should generally land on one then get ported to the other (check both when debugging a shared-code-path issue).
- **matchavez/hockeyrosters** — consumes this repo's release PDFs + `boxscores.json`.
- **matchavez/nzihl-season-data** — separate, covers *completed* box scores across both leagues; this repo only cares about upcoming games.

## Sync note
Keep this file (and a README.md, if one gets added) in sync with every meaningful change. If they drift, flag it to Mat and get approval before publishing the sync rather than doing it silently.
