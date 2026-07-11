"""FAAB waiver assistant.

Run weekly to see available free agents and get help sizing a FAAB bid
against your remaining budget. This is a stub: it lists free agents from
ESPN but bid suggestion logic is not implemented yet.
"""

import argparse

from empire_tools import espn_client
from empire_tools.config import load_config


def list_free_agents(position: str | None = None, size: int = 50):
    league = espn_client.get_league()
    agents = league.free_agents(size=size)
    if position:
        agents = [a for a in agents if a.position == position.upper()]
    for player in agents:
        print(f"{player.name:<25} {player.position:<4} {player.proTeam}")


def main():
    parser = argparse.ArgumentParser(description="Empire League FAAB assistant")
    parser.add_argument("--position", help="Filter free agents by position (e.g. RB, WR)")
    parser.add_argument("--size", type=int, default=50, help="Max number of free agents to list")
    args = parser.parse_args()

    load_config()  # fail fast if config.yaml is missing
    list_free_agents(position=args.position, size=args.size)


if __name__ == "__main__":
    main()
