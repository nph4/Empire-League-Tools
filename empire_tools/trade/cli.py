"""Proposed-trade evaluator.

Score a hypothetical trade between your team and one other team before you
propose or accept it. Prints four letter grades - your rest-of-season and
long-term grades, and the same two for the other team - plus callout lines
about roster needs, the roster limit, and net points/value each way. Like
FAAB and the cheat sheet (and unlike the auction), this is a one-shot
argparse command, not a REPL: a trade is scored once, there's no live
state to keep up with.

    python -m empire_tools.trade eval --give "Player A" "Player B" \\
        --get "Player C" [--team "My Team"] [--with "Other Team"]

`--give`/`--get` are from your point of view. `--with` is optional - the
other team is inferred from whoever currently rosters the `--get` players.
"""

import argparse

from empire_tools import espn_client
from empire_tools.config import load_config
from empire_tools.roster import find_team, needed_positions, requirements_from_espn_slot_counts
from empire_tools.strength.model import (
    DEFAULT_BENCH_DEPTH_WEIGHT,
    DEFAULT_TRADE_Z_SPAN,
    league_positional_strength,
    team_weakness_multipliers,
)
from empire_tools.trade.evaluate import (
    DEFAULT_DEPTH_DISCOUNT,
    DEFAULT_NEED_BOOST,
    DEFAULT_NEED_SWING_CAP,
    SideNeeds,
    SidePlayer,
    TradeConfig,
    evaluate_trade,
)
from empire_tools.valuations import build_value_pool_from_config


def _resolve_from_roster(team, names: list[str], side_label: str) -> list:
    """Match each name to exactly one player on `team.roster`. Raises
    RuntimeError listing any that aren't there or are ambiguous."""
    resolved = []
    missing = []
    for name in names:
        matches = [p for p in team.roster if p.name == name]
        if not matches:
            missing.append(name)
        elif len(matches) > 1:
            raise RuntimeError(
                f"{name!r} matches {len(matches)} players on {team.team_name.strip()!r} - "
                f"can't disambiguate by name."
            )
        else:
            resolved.append(matches[0])
    if missing:
        raise RuntimeError(
            f"Not on {team.team_name.strip()!r}'s roster ({side_label}): " + ", ".join(map(repr, missing))
        )
    return resolved


def _infer_counterparty(league, user_team, get_names: list[str]):
    """Find the one team that rosters every `--get` player. Raises
    RuntimeError with a specific reason when that's not possible."""
    teams_with = {
        name: [t for t in league.teams if any(p.name == name for p in t.roster)]
        for name in get_names
    }

    candidates = set()
    for name, teams in teams_with.items():
        if not teams:
            player = league.player_info(name=name)
            if player is None:
                raise RuntimeError(f"{name!r} not found - check the spelling.")
            raise RuntimeError(f"{name!r} is a free agent; you can't trade for a free agent.")
        candidates |= {t.team_name.strip() for t in teams}

    candidates.discard(user_team.team_name.strip())
    if len(candidates) > 1:
        raise RuntimeError(
            "The --get players are spread across multiple teams "
            f"({', '.join(sorted(candidates))}) - pass --with to name the other team."
        )
    if not candidates:
        raise RuntimeError("Couldn't work out the other team - pass --with.")
    return find_team(league, candidates.pop())


def _points_roster(team) -> list[tuple[str, float]]:
    """(base_position, projected_total_points) per rostered player - the
    projected-points ruler for the league positional-strength model."""
    return [(p.position, float(p.projected_total_points or 0.0)) for p in team.roster]


def _side_strength_rosters(team, received: list, given: list) -> tuple[list, list]:
    """(before, after) `_points_roster`-shaped lists for one side, applying
    the same first-position-match removal for given players that
    `_side_needs` does - but carrying the value each player is worth."""
    before = _points_roster(team)
    after = list(before)
    for p in given:
        match = next((entry for entry in after if entry[0] == p.position), None)
        if match is not None:
            after.remove(match)
    after += [(p.position, float(p.projected_total_points or 0.0)) for p in received]
    return before, after


def _side_needs(
    requirements,
    team,
    received: list,
    given: list,
    weakness_before: dict | None = None,
    weakness_after: dict | None = None,
) -> SideNeeds:
    before = [p.position for p in team.roster]
    after = list(before)
    for p in given:
        if p.position in after:
            after.remove(p.position)
    after += [p.position for p in received]
    return SideNeeds(
        need_before=frozenset(needed_positions(requirements, before)),
        need_after=frozenset(needed_positions(requirements, after)),
        roster_size_before=len(before),
        roster_size_after=len(after),
        bench_spots=requirements.bench_spots,
        roster_capacity=requirements.total_spots,
        weakness_before=weakness_before or {},
        weakness_after=weakness_after or {},
    )


def _grade_cell(model) -> str:
    if model.grade == model.raw_grade:
        return model.grade
    return f"{model.grade}  (raw {model.raw_grade})"


def render_report(result, verbose: bool = False) -> str:
    you, them = result.user, result.counterparty
    you_name, them_name = you.team_name.strip(), them.team_name.strip()
    name_w = max(len(you_name), len(them_name), len("Team")) + 2
    lines = [
        f"Trade — {you_name}  <->  {them_name}",
        "",
        f"{'':<{name_w}}{'Rest-of-season':<20}Long-term",
        f"{you_name:<{name_w}}{_grade_cell(you.ros):<20}{_grade_cell(you.long_term)}",
        f"{them_name:<{name_w}}{_grade_cell(them.ros):<20}{_grade_cell(them.long_term)}",
    ]
    if verbose:
        for side in (you, them):
            lines += [
                "",
                f"{side.team_name.strip()} — value in / out (raw -> need-adjusted):",
                f"  ROS       {side.ros.raw_value_in:7.1f} / {side.ros.raw_value_out:7.1f}"
                f"   ->  {side.ros.value_in:7.1f} / {side.ros.value_out:7.1f}"
                f"   score {side.ros.raw_score:+.3f} -> {side.ros.score:+.3f}",
                f"  Long-term {side.long_term.raw_value_in:7.1f} / {side.long_term.raw_value_out:7.1f}"
                f"   ->  {side.long_term.value_in:7.1f} / {side.long_term.value_out:7.1f}"
                f"   score {side.long_term.raw_score:+.3f}",
            ]
    for side in (you, them):
        lines.append("")
        lines.append(f"{side.team_name.strip()}:")
        for callout in side.callouts:
            lines.append(f"  {callout}")
    return "\n".join(lines)


def evaluate_cli(config: dict, league, args) -> str:
    user_team_name = args.team or config.get("my_team_name")
    if not user_team_name:
        raise RuntimeError("No team specified. Pass --team or set my_team_name in config.yaml.")

    overlap = set(args.give) & set(args.get)
    if overlap:
        raise RuntimeError(f"{', '.join(map(repr, sorted(overlap)))} is on both sides of the trade.")

    user_team = find_team(league, user_team_name)
    counterparty = (
        find_team(league, args.with_)
        if args.with_
        else _infer_counterparty(league, user_team, args.get)
    )

    give_players = _resolve_from_roster(user_team, args.give, "--give")
    get_players = _resolve_from_roster(counterparty, args.get, "--get")

    free_agents = league.free_agents(size=args.size)
    traded = give_players + get_players
    lt_pool = build_value_pool_from_config(config, free_agents + traded)

    def to_side_player(p) -> SidePlayer:
        # projected_total_points is a full-season figure; pre-season that's
        # the same as rest-of-season. TODO: prorate by games remaining for
        # mid-season use.
        return SidePlayer(
            name=p.name,
            position=p.position,
            ros_value=float(p.projected_total_points or 0.0),
            lt_value=float(lt_pool.get(p.name, 0.0)),
        )

    requirements = requirements_from_espn_slot_counts(league.settings.position_slot_counts)
    user_received = [to_side_player(p) for p in get_players]
    user_given = [to_side_player(p) for p in give_players]

    trade_config = config.get("trade", {})
    cfg = TradeConfig(
        need_boost=trade_config.get("need_boost", DEFAULT_NEED_BOOST),
        depth_discount=trade_config.get("depth_discount", DEFAULT_DEPTH_DISCOUNT),
        need_swing_cap=trade_config.get("need_swing_cap", DEFAULT_NEED_SWING_CAP),
    )

    # League-relative positional strength drives the ROS need nudge: a
    # received player at a below-average spot counts for more, one at a
    # position of strength for less. Points ruler only (dynasty value never
    # feeds need). Falls back to the binary need model in deep preseason.
    strength_config = config.get("strength", {})
    bench_weight = strength_config.get("bench_depth_weight", DEFAULT_BENCH_DEPTH_WEIGHT)
    z_span = strength_config.get("trade_z_span", DEFAULT_TRADE_Z_SPAN)
    base_rosters = {t.team_name.strip(): _points_roster(t) for t in league.teams}
    base_strength = league_positional_strength(base_rosters, requirements, bench_weight)

    def weakness_maps(team, received, given):
        """(before, after) position->multiplier dicts for one side. `after`
        recomputes the league with only this team's roster swapped."""
        if base_strength.is_degenerate:
            return {}, {}
        name = team.team_name.strip()

        def multipliers(strength):
            return team_weakness_multipliers(
                strength,
                name,
                need_boost=cfg.need_boost,
                depth_discount=cfg.depth_discount,
                z_span=z_span,
            )

        _, after_roster = _side_strength_rosters(team, received, given)
        after_strength = league_positional_strength(
            {**base_rosters, name: after_roster}, requirements, bench_weight
        )
        return multipliers(base_strength), multipliers(after_strength)

    user_wb, user_wa = weakness_maps(user_team, get_players, give_players)
    cp_wb, cp_wa = weakness_maps(counterparty, give_players, get_players)
    user_needs = _side_needs(requirements, user_team, get_players, give_players, user_wb, user_wa)
    counterparty_needs = _side_needs(
        requirements, counterparty, give_players, get_players, cp_wb, cp_wa
    )

    result = evaluate_trade(
        user_team.team_name.strip(),
        counterparty.team_name.strip(),
        user_received=user_received,
        user_given=user_given,
        user_needs=user_needs,
        counterparty_needs=counterparty_needs,
        cfg=cfg,
    )
    return render_report(result, verbose=args.verbose)


def main():
    parser = argparse.ArgumentParser(description="Empire League trade evaluator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser("eval", help="Grade a proposed trade")
    eval_parser.add_argument(
        "--give", nargs="+", required=True, metavar="NAME", help="Exact names of players you'd send"
    )
    eval_parser.add_argument(
        "--get", nargs="+", required=True, metavar="NAME", help="Exact names of players you'd receive"
    )
    eval_parser.add_argument("--team", help="Your ESPN team name (defaults to my_team_name in config.yaml)")
    eval_parser.add_argument(
        "--with",
        dest="with_",
        metavar="TEAM",
        help="The other team's ESPN name (inferred from the --get players if omitted)",
    )
    eval_parser.add_argument("--size", type=int, default=2000, help="Max free agents to pull from ESPN")
    eval_parser.add_argument("--verbose", action="store_true", help="Also show the underlying value breakdown")

    args = parser.parse_args()
    config = load_config()
    league = espn_client.get_league(config)

    if args.command == "eval":
        try:
            print(evaluate_cli(config, league, args))
        except RuntimeError as e:
            parser.error(str(e))


if __name__ == "__main__":
    main()
