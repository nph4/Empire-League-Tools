"""Draft cheat sheet generator.

Run ahead of the startup auction (and re-run as often as you like between
now and draft day as camp/preseason news comes in) to produce a printable
sheet of every draftable player, grouped by position and tiered by value,
with room for hand-maintained notes and situational flags. Not a live tool
like the auction REPL - there's no draft-day state to keep up with here,
just a document to regenerate.
"""

import argparse

from empire_tools import espn_client
from empire_tools.cheatsheet.build import build_rows
from empire_tools.cheatsheet.notes import load_notes_from_config
from empire_tools.cheatsheet.render import render_csv, render_markdown
from empire_tools.config import load_config
from empire_tools.valuations import build_value_pool_from_config


def generate(config: dict, players: list, position: str | None = None, fmt: str = "markdown") -> str:
    if position:
        players = [p for p in players if p.position == position]

    value_pool = build_value_pool_from_config(config, players)
    notes = load_notes_from_config(config)
    gap_threshold = config.get("cheatsheet", {}).get("tier_gap_threshold", 0.15)

    rows = build_rows(players, value_pool, notes, gap_threshold)
    return render_csv(rows) if fmt == "csv" else render_markdown(rows)


def main():
    parser = argparse.ArgumentParser(description="Empire League draft cheat sheet generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate the cheat sheet")
    generate_parser.add_argument("--position", help="Only include one position (e.g. RB, WR)")
    generate_parser.add_argument("--format", choices=["markdown", "csv"], default="markdown")
    generate_parser.add_argument("--output", help="Write to this file instead of stdout")
    generate_parser.add_argument("--size", type=int, default=2000, help="Max players to pull from ESPN")

    args = parser.parse_args()
    config = load_config()

    if args.command == "generate":
        league = espn_client.get_league(config)
        players = league.free_agents(size=args.size)
        sheet = generate(config, players, position=args.position, fmt=args.format)
        if args.output:
            with open(args.output, "w") as f:
                f.write(sheet)
        else:
            print(sheet)


if __name__ == "__main__":
    main()
