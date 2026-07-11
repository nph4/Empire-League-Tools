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
  interactive REPL for running a live dynasty auction draft. Tracks
  manager budgets and the available player pool as sales are recorded.
- **FAAB assistant** (`python -m empire_tools.faab`) — lists current free
  agents to help size a weekly FAAB bid.

Both tools are early scaffolding; bid/target suggestion logic is not
implemented yet. More tools will be added as the league progresses.
