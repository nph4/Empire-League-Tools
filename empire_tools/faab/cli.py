"""FAAB waiver assistant.

Run weekly to see available free agents and get a suggested FAAB bid sized
against your remaining budget, how the player ranks among free agents at
their position, and whether they'd fill an open starting/flex slot on your
actual current roster.
"""

import argparse

from empire_tools import espn_client
from empire_tools.config import load_config
from empire_tools.faab.suggest import (
    DEFAULT_COMPARISON_POOL_SIZE,
    blend_percentiles,
    format_points_per_game,
    is_injury_reserve,
    live_weight_for_week,
    percentile_within_position,
    suggest_bid,
)
from empire_tools.roster import find_team, needed_positions, requirements_from_espn_slot_counts
from empire_tools.valuations import build_value_pool_from_config


def blended_percentiles(config: dict, league, free_agents: list) -> dict[str, float]:
    """Each free agent's position rank (1.0 = best available), blending
    their `values_csv` dynasty rank with their live ESPN projection rank -
    see `blend_percentiles` / `live_weight_for_week`. Both `list` and `bid`
    rank off this, so the list order matches what drives the bid."""
    faab_config = config.get("faab", {})
    weight = live_weight_for_week(
        league.current_week,
        start=faab_config.get("live_weight_start", 0.4),
        end=faab_config.get("live_weight_end", 0.9),
        ramp_weeks=faab_config.get("live_weight_ramp_weeks", 8),
    )
    top_k = faab_config.get("comparison_pool_size", DEFAULT_COMPARISON_POOL_SIZE)
    dynasty_pool = build_value_pool_from_config(config, free_agents)
    live_pool = {p.name: p.projected_total_points for p in free_agents}
    return {
        p.name: blend_percentiles(
            percentile_within_position(dynasty_pool, free_agents, p.name, top_k),
            percentile_within_position(live_pool, free_agents, p.name, top_k),
            weight,
        )
        for p in free_agents
    }


def list_free_agents(
    free_agents: list,
    percentiles: dict[str, float],
    position: str | None = None,
    include_ir: bool = False,
    size: int = 50,
):
    """Best-ranked free agents first. Position/IR filtering happens before
    the `size` cap, so `--position RB --size 15` shows 15 RBs rather than
    whichever RBs happen to fall in the top 15 overall."""
    hidden = 0
    shown = 0
    for player in sorted(free_agents, key=lambda p: percentiles[p.name], reverse=True):
        if shown >= size:
            break
        if position and player.position != position:
            continue
        if not include_ir and is_injury_reserve(player):
            hidden += 1
            continue
        print(
            f"{player.name:<25} {player.position:<4} {player.proTeam:<4} "
            f"rank {percentiles[player.name]:.2f}  {player.avg_points:5.1f} pts/g"
        )
        shown += 1
    if hidden:
        print(f"\n({hidden} player(s) on injured reserve hidden - pass --include-ir to show)")


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

    if is_injury_reserve(player):
        print(f"Note: {player_name} is on injured reserve and isn't producing right now.")

    remaining_budget = league.settings.acquisition_budget - team.acquisition_budget_spent
    percentile = blended_percentiles(config, league, free_agents)[player_name]
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
    list_parser.add_argument("--pool", type=int, default=2000, help="Max free agents to pull from ESPN")
    list_parser.add_argument(
        "--include-ir", action="store_true", help="Include free agents on injured reserve (hidden by default)"
    )

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
        free_agents = league.free_agents(size=args.pool)
        list_free_agents(
            free_agents,
            blended_percentiles(config, league, free_agents),
            position=args.position,
            include_ir=args.include_ir,
            size=args.size,
        )
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
        player = next(p for p in free_agents if p.name == args.player)
        print(format_points_per_game(player.total_points, player.avg_points, player.projected_avg_points))
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
