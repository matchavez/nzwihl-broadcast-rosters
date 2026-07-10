# memory.md — matchavez/nzwihl-broadcast-rosters

Self-context for Claude. README.md now exists (added 2026-07-11), modeled on the NZIHL sibling's README with corrected current-state details (cron, NZWIHL support, no-cache origin). This repo is the NZWIHL sibling of matchavez/nzihl-broadcast-rosters; same architecture (`src/nzwihl_rosters/{teams,overrides,scraper,schedule,layout,cli}.py`, `tests/`, `boxscores.json` manifest), just the women's league. Last refreshed: 2026-07-11.

## Automation
- Cron `30 17 * * *` UTC (workflow comment says "19:00 UTC" — same stale-comment issue as the NZIHL sibling; trust the actual cron value).
- PDF window 4 days, manifest lookahead 11 days, same decoupling rationale as nzihl-broadcast-rosters.
- `contents: write` permission for `boxscores.json` commits + release publishing.

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
