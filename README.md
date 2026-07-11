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
  the market. Optionally set `values_csv` in `config.yaml` to a `name,value`
  CSV of your own dynasty rankings/values (any scale); players missing from
  it fall back to a value derived from ESPN's projections.
- **FAAB assistant** (`python -m empire_tools.faab list [--position POS]` /
  `python -m empire_tools.faab bid "Player Name" [--team "My Team"]` /
  `python -m empire_tools.faab needs [--team "My Team"]`) — lists current
  free agents, or suggests a dollar bid for one sized against your actual
  remaining FAAB budget (read live from ESPN), how the player ranks among
  free agents at their position, and whether they'd fill an open
  starting/flex slot on your actual current roster (also read live from
  ESPN) — bench-only adds get a discounted suggestion. `--team` defaults
  to `my_team_name` in `config.yaml`.

More tools will be added as the league progresses.
