# Empire-League-Tools

Command-line tools for running my ESPN Fantasy Football **Empire League** —
a [dynasty league with a defined end condition](https://www.dynastynerds.com/dynasty/empire-leagues-how-a-small-variation-could-transform-dynasty-fantasy-football/)
(winning back-to-back championships). The league is set to "open" (public)
on ESPN, so every tool reads league data anonymously through the unofficial
[`espn_api`](https://github.com/cwendt94/espn-api) package — no `espn_s2` /
`SWID` auth cookies are needed, and none should be added.

There's no build system, CI, or packaging. Each tool is a Python module you
run with `python -m empire_tools.<tool>`. This README is the source of truth
for what the repo is and how it's put together; [`CLAUDE.md`](CLAUDE.md) is
Claude Code's working notes — gotchas and a dated change log.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then fill in league_id / year
```

`config.yaml` is gitignored (it's league-specific); `config.example.yaml`
is the tracked template.

## Tools

- **Auction draft assistant** (`python -m empire_tools.auction`) — an
  interactive REPL for running a live dynasty auction draft. Tracks manager
  budgets, roster construction (starters/flex/bench, read from your ESPN
  league's lineup settings), and the available player pool as sales are
  recorded. Suggests a live max bid per player and top targets per manager —
  affordable and ranked by whether they'd fill an open starting/flex slot or
  only the bench — off your own player values, adjusted in real time as the
  draft's actual spending inflates or deflates the market. Commands:
  `sold "<player>" <amount> "<manager>"`, `budgets`, `available [POSITION]`,
  `suggest "<player>"`, `targets "<manager>"`, `needs "<manager>"`.
- **FAAB assistant** (`python -m empire_tools.faab list [--position POS]` /
  `bid "Player Name" [--team "My Team"]` / `needs [--team "My Team"]`) —
  lists current free agents, or suggests a dollar waiver bid for one sized
  against your actual remaining FAAB budget (read live from ESPN), how the
  player ranks among free agents at their position, and whether they'd fill
  an open starting/flex slot on your current roster — bench-only adds get a
  discounted suggestion. `--team` defaults to `my_team_name`.
- **Draft cheat sheet** (`python -m empire_tools.cheatsheet generate
  [--position POS] [--format markdown|csv] [--output PATH]`) — a printable
  pre-draft sheet of every draftable player, grouped by position and tiered
  by value, meant to be regenerated as camp/preseason news comes in.
  Supports an optional hand-maintained overlay CSV (`cheatsheet.notes_csv`)
  for tier overrides, situational flags, notes, and a `window_fit`
  multiplier that nudges a player's rank toward the league's real
  win-timing target. Auto-flags known in-league fan-bias teams
  (`cheatsheet.fan_bias_teams`) and mid-tier TEs.
- **Trade evaluator** (`python -m empire_tools.trade eval --give "Player A"
  "Player B" --get "Player C" [--team "My Team"] [--with "Other Team"]`) —
  grades a proposed trade from your side *and* the other team's: a
  rest-of-season letter grade (from ESPN season projections) and a
  long-term one (from your dynasty value pool), for each team, against that
  team's open roster needs. Calls out filled/opened starting-lineup holes,
  going over the roster limit, and the net points/value each way. `--with`
  is optional — the other team is inferred from whoever rosters the `--get`
  players. `--team` defaults to `my_team_name`.

## Configuration

All settings live in `config.yaml`. Roster construction (how many
starters/flex/bench slots, IR) is **not** configured — it's read from the
ESPN league's lineup settings.

| Key | Used by | Notes |
|---|---|---|
| `league_id`, `year` | everything | the ESPN league to read |
| `my_team_name` | faab, trade | default team for `--team`; must match `Team.team_name` exactly |
| `values_csv` | auction, faab, cheatsheet, trade | path to your dynasty rankings/values (see below); optional — omit to rely on the ESPN-projection fallback for every player |
| `values_csv_rank_half_life` | valuations | only for a FantasyPros rankings export: how many ranks it takes the derived value to halve (default 30; lower concentrates value at the top) |
| `auction.budget_per_manager` | auction | dollars per manager |
| `faab.max_bid_share` | faab | cap on one bid as a fraction of remaining budget (default 0.35) |
| `faab.bench_only_discount` | faab | multiplier when an add wouldn't fill a starting/flex slot (default 0.4) |
| `cheatsheet.notes_csv` | cheatsheet | optional hand-maintained overlay (`name,tier_override,flags,notes,window_fit`) |
| `cheatsheet.tier_gap_threshold` | cheatsheet | relative value drop that starts a new tier (default 0.15) |
| `cheatsheet.fan_bias_teams` | cheatsheet | `proTeam -> flag text` map for known homer-bias teams |
| `trade.need_boost` / `trade.depth_discount` | trade | soft need nudges on the rest-of-season grade (defaults 1.10 / 0.90) |
| `trade.need_swing_cap` | trade | hard cap on how far that nudge can move the score (default 0.10) |

**`values_csv` shapes** (auto-detected from the header by
`valuations.load_csv_values`):

- `name,value` rows — any scale; only relative order/magnitude matters
  (e.g. a KeepTradeCut export).
- A raw FantasyPros *rankings* export
  (`RK,TIERS,PLAYER NAME,...`) — has ranks, no values, so the overall rank
  (`AVG.` when present, else `RK`) is mapped to a value via exponential
  decay. This is the export the FantasyPros website gives you.

Any ESPN-known player missing from the CSV falls back to a value derived
from ESPN's `projected_total_points`, scaled so it can't outrank anyone
explicitly in the CSV (a missing name is treated as replacement-level).

The actual data files are kept in `Ranking CSVs/` (FantasyPros exports,
`player_values.csv`) and `Cheetsheet/` (generated sheets,
`cheatsheet_notes.csv`).

## Architecture

- **One ESPN entry point.** `empire_tools/espn_client.get_league(config)`
  wraps `espn_api.football.League`. Every module goes through it rather than
  importing `espn_api` directly — that's what centralizes the "no auth
  needed" assumption.
- **Shared value model.** `empire_tools/valuations.py` builds a scale-free
  `{player_name: value}` pool from `values_csv` plus the ESPN-projection
  fallback described under Configuration. `build_value_pool_from_config` is
  the entry point; every tool that needs player values uses it rather than
  rolling its own.
- **Shared roster model.** `empire_tools/roster.py` —
  `requirements_from_espn_slot_counts` turns ESPN's
  `position_slot_counts` into a `RosterRequirements` (starters by position,
  one pooled flex bucket, bench; IR tracked separately and left out of
  `total_spots`). `needed_positions(requirements, rostered_positions)` is a
  pure function returning which base positions would still fill an open
  starting/flex slot. `find_team(league, name)` is a shared exact-name
  lookup (tolerant of ESPN's stray whitespace).
- **Pure logic vs. CLI, in every tool.** The decision logic lives in an
  ESPN-free, I/O-free module (`state.py` / `suggest.py` / `evaluate.py` /
  `tiers.py` / `build.py` …) that's unit-tested directly. A thin `cli.py`
  does the ESPN wiring, calls the pure layer, and prints. New logic goes in
  the pure module.
- **REPL vs. argparse.** The live auction is a `cmd.Cmd` REPL — it has to
  keep up with a timed draft, so it's built for fast keyboard entry.
  Everything else (faab, cheatsheet, trade) is one-shot argparse
  subcommands: there's no live state to track.
- **Value pool pre-draft.** Before a draft everyone is a free agent, so the
  auction and cheat sheet pull the candidate pool with
  `league.free_agents(size=2000)`.
- **Testing.** `pytest`, no mocking library — ESPN is never contacted in
  tests. Pure functions are tested directly with small local `@dataclass`
  fakes and dict-literal config; CLIs aren't tested. No linter or formatter
  is configured.

```bash
pytest                                   # full suite
pytest tests/test_auction_state.py -q     # one module
```

## Adding a tool

1. `empire_tools/<tool>/__init__.py` (empty) and `__main__.py`
   (`from empire_tools.<tool>.cli import main` + a `__main__` guard).
2. Put the decision logic in a pure module — no `espn_api`, `config`, or
   I/O imports — so it can be unit-tested like the others.
3. `cli.py`: `load_config()` → `espn_client.get_league(config)` → resolve
   inputs → call the pure layer → print. Raise `RuntimeError` for user
   errors and convert them with `parser.error(...)`.
4. Use argparse subcommands unless the tool must keep up with live state
   (then a REPL, like the auction).
5. Reuse `valuations.build_value_pool_from_config`,
   `roster.requirements_from_espn_slot_counts` / `needed_positions` /
   `find_team` rather than re-deriving any of it.
6. New settings go under a `<tool>:` section, read with
   `config.get("<tool>", {}).get("key", default)`. Add them to
   `config.example.yaml` and to the Configuration table above.
7. `tests/test_<tool>_*.py` — pure functions, dataclass fakes, dict config.
8. Add a Tools bullet here; record any gotchas or design rationale in
   [`CLAUDE.md`](CLAUDE.md).

## More context

[`CLAUDE.md`](CLAUDE.md) is Claude Code's working notes — hard-won gotchas
(ESPN quirks, counterintuitive model behavior, live-draft lessons) and a
dated log of non-obvious changes. Worth a look if something behaves
unexpectedly.
