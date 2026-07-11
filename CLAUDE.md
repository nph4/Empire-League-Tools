# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A collection of tools for running an ESPN Fantasy Football **Empire League**
— a Dynasty league with a defined end condition (winning back-to-back
championships). The league is configured as "open" (public) on ESPN, so all
tools read league data anonymously via the unofficial `espn_api` package —
no `espn_s2`/`SWID` auth cookies are needed or should be added.

The first tool is a live auction-draft assistant; a FAAB (waiver budget)
assistant follows. More tools will be added over time as the league's needs
come up (see `empire_tools/` for the current set).

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # fill in league_id/year — this file is gitignored

# Run the tools
python -m empire_tools.auction   # interactive auction draft REPL
python -m empire_tools.faab      # FAAB free-agent listing

# Tests
pytest                            # full suite
pytest tests/test_auction_state.py::test_max_bid_reserves_a_dollar_per_remaining_roster_spot  # single test
```

There is no linter/formatter configured yet.

## Architecture

- `empire_tools/config.py` — loads `config.yaml` (league_id, year, auction
  budget/roster settings). `config.yaml` is gitignored since it's
  league-specific; `config.example.yaml` is the template.
- `empire_tools/espn_client.py` — the single point of contact with ESPN,
  wrapping `espn_api.football.League`. All other modules should go through
  this rather than importing `espn_api` directly, since it's what
  centralizes the "no auth needed" assumption.
- `empire_tools/auction/` — the live draft assistant.
  - `state.py` — `DraftState`/`Manager`/`Player` dataclasses: pure
    bookkeeping (budgets, available pool, sale history) with no ESPN or I/O
    dependency, hence directly unit-testable (see `tests/test_auction_state.py`).
    `DraftState.max_bid` encodes the standard auction-budget rule of
    reserving $1 per remaining roster spot.
  - `valuations.py` — builds the baseline `{player_name: value}` pool the
    bid model runs on. Primary source is a user-supplied CSV
    (`auction.values_csv` in `config.yaml`, any name/value scale — only
    relative order/magnitude matters, e.g. a KeepTradeCut or FantasyPros
    dynasty export). Any ESPN-known player missing from the CSV falls back
    to a value derived from ESPN's `projected_total_points`, scaled so a
    fallback player can never outrank someone explicitly ranked in the CSV
    (a missing name is assumed replacement-level, not unranked-but-elite —
    true for rookies too, since dynasty CSVs are expected to include them).
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
    (`<= DraftState.max_bid`) by that live suggested bid, descending.
  - `cli.py` — a `cmd.Cmd` REPL (`python -m empire_tools.auction`) built for
    rapid keyboard entry during a live draft: `sold "<player>" <amount>
    "<manager>"`, `budgets`, `available [POSITION]` (now shows live
    suggested bid per player), `suggest "<player>"`, `targets "<manager>"`.
    A REPL was chosen over a notebook or web UI specifically because the
    tool needs to keep up with a live, time-pressured auction.
- `empire_tools/faab/` — weekly FAAB helper, currently just lists free
  agents (`cli.py`); bid-sizing logic is not yet implemented. It's a
  natural candidate to reuse `valuations.py`/`suggest.py` once FAAB gets
  built out, since the "value pool" concept isn't auction-specific.

Positional roster-need awareness (e.g. "this manager still needs a
starting TE") is not modeled anywhere yet — `suggest_targets` only reasons
about affordability, not roster construction. That's the main known gap if
extending the targeting logic further.
