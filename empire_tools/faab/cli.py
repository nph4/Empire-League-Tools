"""FAAB waiver assistant.

Run weekly to see available free agents and get a suggested FAAB bid sized
against your remaining budget, how the player ranks among free agents at
their position, and whether they'd fill an open starting/flex slot on your
actual current roster.
"""

import argparse

from empire_tools import espn_client
from empire_tools.config import load_config
from empire_tools.faab.suggest import percentile_within_position, suggest_bid
from empire_tools.roster import needed_positions, requirements_from_espn_slot_counts
from empire_tools.valuations import build_value_pool_from_config


def list_free_agents(free_agents: list, position: str | None = None):
    for player in free_agents:
        if position and player.position != position:
            continue
        print(f"{player.name:<25} {player.position:<4} {player.proTeam}")


def find_team(league, team_name: str):
    team = next((t for t in league.teams if t.team_name == team_name), None)
    if team is None:
        raise RuntimeError(f"No team named {team_name!r} in this league.")
    return team


def team_needed_positions(league, team) -> set[str]:
    requirements = requirements_from_espn_slot_counts(league.settings.position_slot_counts)
    rostered_positions = [p.position for p in team.roster]
    return needed_positions(requirements, rostered_positions)


def suggest_bid_for_player(config: dict, league, free_agents: list, player_name: str, team_name: str) -> int:
    if not league.settings.faab:
        raise RuntimeError("This league is not configured for FAAB (dollar) waivers.")

    team = find_team(league, team_name)

    player = next((p for p in free_agents if p.name == player_name), None)
    if player is None:
        raise RuntimeError(f"{player_name!r} is not a free agent right now.")

    remaining_budget = league.settings.acquisition_budget - team.acquisition_budget_spent
    value_pool = build_value_pool_from_config(config, free_agents)
    percentile = percentile_within_position(value_pool, free_agents, player_name)
    fills_need = player.position in team_needed_positions(league, team)

    faab_config = config.get("faab", {})
    max_share = faab_config.get("max_bid_share", 0.35)
    bench_only_discount = faab_config.get("bench_only_discount", 0.4)
    return suggest_bid(remaining_budget, percentile, fills_need, max_share, bench_only_discount)


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

    needs_parser = subparsers.add_parser("needs", help="Show remaining roster requirements for a team")
    needs_parser.add_argument("--team", help="Your ESPN team name (defaults to my_team_name in config.yaml)")

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
    elif args.command == "needs":
        team_name = args.team or config.get("my_team_name")
        if not team_name:
            parser.error("No team specified. Pass --team or set my_team_name in config.yaml.")
        try:
            team = find_team(league, team_name)
        except RuntimeError as e:
            parser.error(str(e))
        needed = team_needed_positions(league, team)
        print(", ".join(sorted(needed)) if needed else "No open starting/flex slots")


if __name__ == "__main__":
    main()
