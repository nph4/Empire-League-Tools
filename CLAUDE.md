# CLAUDE.md

Claude Code's working notes for this repo. **[`README.md`](README.md) is the
source of truth** for what this is, the architecture, the conventions, the
config keys, and how to add a tool — read that first. This file is for the
things that aren't in the code or the README: hard-won gotchas that would
otherwise have to be rediscovered, and a dated log of non-obvious changes.

## Gotchas

- **ESPN team names carry stray whitespace.** One manager's name is
  literally `"Burms Burners "` — trailing space in `Team.team_name`.
  `roster.find_team` strips both sides, but `auction`'s `sold` / `suggest`
  / `targets` match the manager name exactly. If a lookup fails on a name
  that's clearly right on screen, suspect whitespace before a typo —
  `budgets` output, or `repr()` on `espn_client.get_league().teams`,
  reveals it.

- **Auction inflation/deflation direction is counterintuitive.**
  `auction/suggest.py` recomputes each player's share of *remaining*
  spendable dollars against their share of the *remaining* pool value, per
  call — no separate inflation multiplier. So money spent *above* a
  player's fair share deflates everyone left (fixed total budget, same
  value removed for more money); money spent *under* fair share inflates
  the rest. The test names in `tests/test_suggest.py` spell this out — read
  them before "fixing" the direction.

- **`DraftState.max_bid` needs no cross-check against ESPN.** ESPN's own
  bid box enforces the identical $1-per-remaining-roster-spot rule
  client-side.

- **Auction nomination minimum raise is $1.** Joining a bid on a player
  someone just nominated at $1 costs $2, not $1.

- **IR slots are excluded from `RosterRequirements.total_spots`** (and
  everything built on it). They're roster capacity but you don't draft or
  bid into them — counting them would inflate the auction's max-bid
  reserve and the bench progress readouts.

- **The auction REPL can be co-piloted over a named pipe.** To drive it
  from another process (e.g. an agent watching the ESPN draft room in a
  browser while a human bids): `mkfifo` a fifo, keep a `sleep infinity`
  writer open on it so the reader never sees EOF between commands, launch
  `python -m empire_tools.auction < fifo > log 2>&1 &`, then append
  commands to the fifo and tail the log from anywhere.

- **FantasyPros' API is free-tier only** — the key caps responses at 10
  rows, so it's useless for a full ranking. Use the website's CSV export
  instead; `valuations.load_csv_values` auto-detects that shape and maps
  its ranks to a value curve. (Also saved as a memory.)

- **The FantasyPros dynasty export has an unused `AGE` column** (and a
  position rank inside `POS`, e.g. `WR11`). `valuations._rankings_to_values`
  reads only the name and overall rank and drops the rest. That `AGE`
  column is the lever if a value model ever needs an age signal — ESPN
  exposes none.

- **Trade evaluator is deliberately minimal.** Rest-of-season grade =
  ESPN `projected_total_points`; long-term grade = a plain value-in vs
  value-out delta on the dynasty pool — no aging curve, no `window_fit`
  overlay, no season counter. Positional need is a soft nudge on the
  rest-of-season grade *only*, clamped by `trade.need_swing_cap`; when
  neither side of the trade touches a need, the boost and discount cancel
  out. `raw_grade` is printed next to `grade` so the nudge stays visible.
  See the `trade-evaluator-design-decisions` memory for what was
  considered and turned down.

- **`cheatsheet` config key vs. code param name mismatch.** The config key
  is `cheatsheet.fan_bias_teams`; the `build_rows` parameter it feeds is
  `team_bias_flags`. Same thing, two names.

## Change log

Newest first. Dated, and only for changes that aren't obvious from `git
log` alone.

- **2026-09-07 — README / CLAUDE.md split.** Restructured the docs to match
  the `Homelab-IaC` repo: `README.md` is now the source of truth
  (architecture, conventions, configuration table, "adding a tool"), and
  this file is working notes — the gotchas above plus this log. The old
  CLAUDE.md's deep module-by-module design prose was distilled into
  README's leaner Architecture section; the per-module "why" that didn't
  survive the trim lives in the code and its tests.

- **2026-09-07 — Trade evaluator added.** New `empire_tools/trade/` with an
  `eval` subcommand; four letter grades (your rest-of-season and
  long-term, plus the counterparty's). `find_team` moved out of
  `faab/cli.py` into `roster.py` so both tools share it. New `trade:`
  config section. See the "Trade evaluator is deliberately minimal" gotcha.

- **2026-09-07 — Repo file cleanup.** Cheat-sheet artifacts moved into
  `Cheetsheet/`, FantasyPros exports and `player_values.csv` into
  `Ranking CSVs/`; `values_csv` / `notes_csv` paths in both config files
  updated to match. LibreOffice lock files (`.~lock.*#`) added to
  `.gitignore`.
