"""FAAB waiver assistant.

Run weekly to see available free agents and get a suggested FAAB bid sized
against your remaining budget and how the player ranks among free agents
at their position.
"""

import argparse

from empire_tools import espn_client
from empire_tools.config import load_config
from empire_tools.faab.suggest import percentile_within_position, suggest_bid
from empire_tools.valuations import build_value_pool_from_config


def list_free_agents(free_agents: list, position: str | None = None):
    for player in free_agents:
        if position and player.position != position:
            continue
        print(f"{player.name:<25} {player.position:<4} {player.proTeam}")


def suggest_bid_for_player(config: dict, league, free_agents: list, player_name: str, team_name: str) -> int:
    if not league.settings.faab:
        raise RuntimeError("This league is not configured for FAAB (dollar) waivers.")

    team = next((t for t in league.teams if t.team_name == team_name), None)
    if team is None:
        raise RuntimeError(f"No team named {team_name!r} in this league.")

    if not any(p.name == player_name for p in free_agents):
        raise RuntimeError(f"{player_name!r} is not a free agent right now.")

    remaining_budget = league.settings.acquisition_budget - team.acquisition_budget_spent
    value_pool = build_value_pool_from_config(config, free_agents)
    percentile = percentile_within_position(value_pool, free_agents, player_name)
    max_share = config.get("faab", {}).get("max_bid_share", 0.35)
    return suggest_bid(remaining_budget, percentile, max_share)


def main():
    parser = argparse.ArgumentParser(description="Empire League FAAB assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List current free agents")
    list_parser.add_argument("--position", help="Filter by position (e.g. RB, WR)")
    list_parser.add_argument("--size", type=int, default=50, help="Max number of free agents to list")

    bid_parser = subparsers.add_parser("bid", help="Suggest a FAAB bid for a free agent")
    bid_parser.add_argument("player", help="Exact free agent name")
    bid_parser.add_argument("--team", help="Your ESPN team name (defaults to my_team_name in config.yaml)")
    bid_parser.add_argument("--size", type=int, default=2000, help="Max free agents to pull from ESPN")

    args = parser.parse_args()
    config = load_config()
    league = espn_client.get_league(config)

    if args.command == "list":
        list_free_agents(league.free_agents(size=args.size), position=args.position)
    elif args.command == "bid":
        team_name = args.team or config.get("my_team_name")
        if not team_name:
            parser.error("No team specified. Pass --team or set my_team_name in config.yaml.")
        free_agents = league.free_agents(size=args.size)
        try:
            bid = suggest_bid_for_player(config, league, free_agents, args.player, team_name)
        except RuntimeError as e:
            parser.error(str(e))
        print(f"Suggested bid for {args.player}: ${bid}")


if __name__ == "__main__":
    main()
