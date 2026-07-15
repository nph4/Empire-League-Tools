# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A collection of tools for running an ESPN Fantasy Football **Empire League**
— a Dynasty league with a defined end condition (winning back-to-back
championships). The league is configured as "open" (public) on ESPN, so all
tools read league data anonymously via the unofficial `espn_api` package —
no `espn_s2`/`SWID` auth cookies are needed or should be added.

There's a live auction-draft assistant, a FAAB (waiver budget) bid
assistant, and a pre-draft cheat sheet generator. More tools will be added
over time as the league's needs come up (see `empire_tools/` for the
current set).

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # fill in league_id/year — this file is gitignored

# Run the tools
python -m empire_tools.auction               # interactive auction draft REPL
python -m empire_tools.faab list [--position RB]
python -m empire_tools.faab bid "Player Name" [--team "My Team"]
python -m empire_tools.faab needs [--team "My Team"]
python -m empire_tools.cheatsheet generate [--position RB] [--format markdown|csv] [--output PATH]

# Tests
pytest                            # full suite
pytest tests/test_auction_state.py::test_max_bid_reserves_a_dollar_per_remaining_roster_spot  # single test
```

There is no linter/formatter configured yet.

## Architecture

- `empire_tools/config.py` — loads `config.yaml` (league_id, year,
  `my_team_name`, auction budget, FAAB settings, cheat sheet settings,
  shared `values_csv` path). `config.yaml` is gitignored since it's league-specific;
  `config.example.yaml` is the template. Roster construction (starters,
  flex, bench) is *not* configured here — it's read from ESPN, see below.
- `empire_tools/espn_client.py` — the single point of contact with ESPN,
  wrapping `espn_api.football.League`. All other modules should go through
  this rather than importing `espn_api` directly, since it's what
  centralizes the "no auth needed" assumption.
- `empire_tools/valuations.py` — builds the baseline `{player_name: value}`
  pool that both the auction and FAAB bid models run on. Primary source is
  a user-supplied CSV (`values_csv` in `config.yaml`, any name/value
  scale — only relative order/magnitude matters, e.g. a KeepTradeCut or
  FantasyPros dynasty export). Any ESPN-known player missing from the CSV
  falls back to a value derived from ESPN's `projected_total_points`,
  scaled so a fallback player can never outrank someone explicitly ranked
  in the CSV (a missing name is assumed replacement-level, not
  unranked-but-elite — true for rookies too, since dynasty CSVs are
  expected to include them). `build_value_pool_from_config` is the usual
  entry point; it's shared rather than duplicated per-tool.
- `empire_tools/roster.py` — roster construction shared by both tools.
  `RosterRequirements` models actual roster construction (starters by
  position, a pooled flex bucket, bench) rather than a flat spot count;
  `requirements_from_espn_slot_counts` translates ESPN's
  `League.settings.position_slot_counts` into one, so roster rules are read
  automatically instead of duplicated in config. It assumes a single flex
  slot type (true for standard leagues, including this one) — multiple
  distinct flex types get pooled into one bucket with the union of
  eligible positions, an approximation for leagues using more than one.
  `needed_positions(requirements, rostered_positions)` is a pure function
  that greedily assigns each already-rostered position to the most
  specific open slot (exact position, then flex) and returns what's still
  open — used by FAAB directly against a team's live ESPN roster, and
  mirrored by the auction's incremental `DraftState._fill_slot`/
  `needed_positions` (see below) since a live draft needs to track slot
  state *as it fills up*, not just compute it once from a finished roster.
- `empire_tools/auction/` — the live draft assistant.
  - `state.py` — `DraftState`/`Manager`/`Player` dataclasses: pure
    bookkeeping (budgets, available pool, sale history, roster slots) with
    no ESPN or I/O dependency, hence directly unit-testable (see
    `tests/test_auction_state.py`, `tests/test_roster_requirements.py`).
    `DraftState.max_bid` encodes the standard auction-budget rule of
    reserving $1 per remaining roster spot. `DraftState.record_sale` fills
    a drafted player into the most specific open slot via `_fill_slot`:
    exact starter position first, then flex, then bench (same ordering as
    `roster.needed_positions`, just tracked incrementally on `Manager`
    instead of recomputed from scratch each time).
    `DraftState.needed_positions` returns which positions would still fill
    a *starting* (non-bench) slot for a manager right now.
  - `suggest.py` — turns the value pool into live dollar suggestions.
    `suggest_bid` gives a player their share of *remaining* spendable
    dollars (total remaining manager budgets minus $1 per remaining roster
    spot) proportional to their share of the *remaining* pool's total
    value. Recomputing this ratio against current state — rather than
    tracking a separate inflation multiplier — makes inflation/deflation
    fall out automatically: money spent *above* a player's fair share
    deflates everyone left (fixed total budget, same value removed for
    more money); money spent *under* fair share inflates the rest. This is
    counterintuitive on first read — see the test names in
    `tests/test_suggest.py` before "fixing" the direction.
    `suggest_targets` ranks available players a manager can actually afford
    (`<= DraftState.max_bid`), with players that fill an open starting/flex
    slot (`DraftState.needed_positions`) ranked ahead of bench-only value —
    the dollar value itself is need-agnostic; need only affects ordering.
  - `cli.py` — a `cmd.Cmd` REPL (`python -m empire_tools.auction`) built for
    rapid keyboard entry during a live draft: `sold "<player>" <amount>
    "<manager>"`, `budgets`, `available [POSITION]` (shows live suggested
    bid per player), `suggest "<player>"`, `targets "<manager>"` (tags each
    as NEEDED or bench), `needs "<manager>"` (remaining roster requirements).
    A REPL was chosen over a notebook or web UI specifically because the
    tool needs to keep up with a live, time-pressured auction.
- `empire_tools/faab/` — weekly FAAB waiver bid assistant. Unlike the
  auction draft, ESPN already tracks real budget state
  (`League.settings.acquisition_budget`, `Team.acquisition_budget_spent`),
  so there's no local bookkeeping equivalent to `DraftState` here.
  - `suggest.py` — `percentile_within_position` ranks a free agent's
    baseline value (from `valuations.py`) against other free agents
    currently available *at the same position* (0 = worst, 1 = best; a
    lone player at their position is treated as best). `suggest_bid`
    converts that into a dollar suggestion as `max_share * percentile**2`
    of remaining budget (`faab.max_bid_share` in config, default 0.35) —
    squared so budget concentrates on genuine difference-makers rather
    than spreading evenly across the waiver wire — then applies
    `faab.bench_only_discount` (default 0.4) if the player wouldn't fill
    an open starting/flex slot on your roster (`fills_need=False`); value
    alone doesn't justify full budget for a likely bench stash.
  - `cli.py` — argparse subcommands (not a REPL — there's no live
    competitive state to keep up with mid-bid, unlike the auction):
    `python -m empire_tools.faab list [--position POS]`,
    `python -m empire_tools.faab bid "<player>" [--team "<name>"]`, and
    `python -m empire_tools.faab needs [--team "<name>"]`. `--team`
    defaults to `my_team_name` in `config.yaml`. `team_needed_positions`
    pulls the team's *actual current* ESPN roster (`Team.roster`, real
    add/drop history — no local tracking needed, unlike the auction) and
    runs it through `roster.needed_positions`.
- `empire_tools/cheatsheet/` — generates a printable pre-draft cheat sheet
  for the startup auction: every draftable player (same `league.free_agents(size=2000)`
  "everyone's a free agent" trick `auction/cli.py` uses pre-draft), grouped
  by position and tiered by value, with room for a hand-maintained overlay
  of tier overrides, situational flags, and notes that's meant to be
  updated repeatedly between now and draft day as camp/preseason news comes
  in. Not a live/REPL tool — like FAAB, there's no draft-day state to keep
  up with here, just a document to regenerate.
  - `tiers.py` — `assign_tiers`/`assign_tiers_by_position` are pure functions
    with no ESPN/CSV dependency: given a position's values sorted
    descending, a new tier starts wherever the drop to the next value
    exceeds `gap_threshold` as a fraction of the higher value (config
    `cheatsheet.tier_gap_threshold`, default 0.15) — tiers are computed
    independently per position, since a tier-1 QB and a tier-1 RB aren't
    held to the same bar.
  - `notes.py` — `load_notes`/`load_notes_from_config` read the optional
    `cheatsheet.notes_csv` (`name,tier_override,flags,notes,window_fit`
    rows) into `{name: PlayerNotes}`, same optional-CSV pattern as
    `values_csv` in `valuations.py` — a missing file just means no manual
    annotations yet. This file is the part of the cheat sheet meant to be
    hand-edited as camp/preseason news comes in; regenerating the sheet
    only reads it, never overwrites it. `window_fit_multiplier` (default
    1.0) is a hand-entered adjustment for how well a player fits this
    league's actual win-timing target — the payout structure means the
    real prize is winning two *consecutive* seasons (4&5 or 5&6 of this
    iteration), not generic "peak dynasty value ASAP" — since there's no
    ESPN-sourced age/experience signal to compute that automatically.
  - `build.py` — `build_rows` merges the value pool (`valuations.py`), auto
    tiers (`tiers.py`), and the manual overlay (`notes.py`) into
    `CheatSheetRow`s. `window_fit_multiplier` is applied to a player's
    value *before* tiering/ranking, since a deliberate win-timing call
    should actually move the rank, not just be a footnote; when it isn't
    1.0 a `window×{multiplier}` flag makes the adjustment visible next to
    the number it changed. Everything else is annotate-don't-rewrite: a
    `tier_override` from the notes CSV wins over the auto-computed tier,
    `flags` merges an auto flag pulled straight from ESPN's
    `Player.injuryStatus` (when not healthy/`ACTIVE`), an optional
    `team_bias_flags` config map (pro_team -> flag text, e.g. this
    league's Vikings/Commanders fan-heavy homer bias — see
    `config.example.yaml`) keyed by ESPN's `proTeam`, a hardcoded
    `mid-tier-TE` flag (personal draft philosophy: first TE or last TE,
    skip the middle — flagged whenever a TE's tier is strictly between the
    best and worst TE tier), and any manual flags from the notes CSV. Rows
    sort by `(position, tier, -value)` — read-this-section-best-tier-first
    order for a printed sheet.
  - `render.py` — pure formatting, no I/O: `render_markdown` (one table per
    position, for printing) and `render_csv` (flat rows, for
    Sheets/Excel filtering).
  - `cli.py` — argparse, single `generate` subcommand (no REPL, same
    reasoning as FAAB): `python -m empire_tools.cheatsheet generate
    [--position POS] [--format markdown|csv] [--output PATH]`.
