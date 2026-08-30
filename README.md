# Empire-League-Tools

Some tools to help me with my Dynasty Fantasy Football league.

This is an [Empire League](https://www.dynastynerds.com/dynasty/empire-leagues-how-a-small-variation-could-transform-dynasty-fantasy-football/) —
a Dynasty league with a defined end condition (winning back-to-back
championships) — run on ESPN Fantasy Football. The league is configured as
"open" (public), so these tools read league data anonymously; no ESPN login
is required.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml  # then fill in your league_id/year
```

## Tools

- **Auction draft assistant** (`python -m empire_tools.auction`) — an
  interactive REPL for running a live dynasty auction draft. Tracks manager
  budgets, roster construction (starters/flex/bench, read automatically
  from your ESPN league's lineup settings), and the available player pool
  as sales are recorded. Suggests a live max bid per player and top targets
  per manager — affordable and ranked by whether they'd fill an open
  starting/flex slot or only the bench — based on your own player values,
  adjusted in real time as the draft's actual spending inflates or deflates
  the market. Optionally set `values_csv` in `config.yaml` to your own
  dynasty rankings — either a `name,value` CSV (any scale) or a raw
  FantasyPros rankings export downloaded from their site, which is
  converted from ranks to a value curve automatically; players missing
  from it fall back to a value derived from ESPN's projections.
- **FAAB assistant** (`python -m empire_tools.faab list [--position POS]` /
  `python -m empire_tools.faab bid "Player Name" [--team "My Team"]` /
  `python -m empire_tools.faab needs [--team "My Team"]`) — lists current
  free agents, or suggests a dollar bid for one sized against your actual
  remaining FAAB budget (read live from ESPN), how the player ranks among
  free agents at their position, and whether they'd fill an open
  starting/flex slot on your actual current roster (also read live from
  ESPN) — bench-only adds get a discounted suggestion. `--team` defaults
  to `my_team_name` in `config.yaml`.
- **Draft cheat sheet** (`python -m empire_tools.cheatsheet generate
  [--position POS] [--format markdown|csv] [--output PATH]`) — generates a
  printable pre-draft sheet of every draftable player, grouped by position
  and tiered by value, meant to be regenerated as often as you like between
  now and draft day as camp/preseason news comes in. Supports an optional
  hand-maintained overlay CSV (`cheatsheet.notes_csv` in `config.yaml`) for
  tier overrides, situational flags, free-text notes, and a `window_fit`
  multiplier for hand-adjusting a player's rank toward your league's actual
  win-timing target rather than generic dynasty value. Also auto-flags
  known in-league fan-bias teams (`cheatsheet.fan_bias_teams`) and mid-tier
  TEs (if you'd rather pay for the top tier or punt to the waiver wire).

More tools will be added as the league progresses.
