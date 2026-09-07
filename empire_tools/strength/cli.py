"""League-relative positional strength report.

For every base position, scores a team's corps against the rest of the
league on two rulers side by side - ESPN season-point projections and the
dynasty value pool - and flags the positions where you're a relative weak
spot. Distinct from `faab needs` / the auction's `needs`, which only ask
whether a starting slot is literally unfilled.

    python -m empire_tools.strength report [--team "My Team"] [--all] \\
        [--metric points|value|both]

`--team` defaults to `my_team_name`. `--all` shows every team at every
position instead of just one.
"""

import argparse

from empire_tools import espn_client
from empire_tools.config import load_config
from empire_tools.roster import find_team, requirements_from_espn_slot_counts
from empire_tools.strength.model import (
    DEFAULT_BENCH_DEPTH_WEIGHT,
    WEAK_Z,
    LeagueStrength,
    TeamPositionStanding,
    classify_strength,
    league_positional_strength,
)
from empire_tools.valuations import build_value_pool_from_config

POSITION_ORDER = ["QB", "RB", "WR", "TE", "D/ST", "K"]


def build_strengths(config: dict, league) -> tuple[LeagueStrength, LeagueStrength]:
    """(points, value) league strengths - the ESPN projected-points ruler
    and the dynasty value pool, both over every rostered player."""
    requirements = requirements_from_espn_slot_counts(league.settings.position_slot_counts)
    bench_weight = config.get("strength", {}).get("bench_depth_weight", DEFAULT_BENCH_DEPTH_WEIGHT)
    teams = list(league.teams)

    points_rosters = {
        t.team_name.strip(): [(p.position, float(p.projected_total_points or 0.0)) for p in t.roster]
        for t in teams
    }
    pool = build_value_pool_from_config(config, [p for t in teams for p in t.roster])
    value_rosters = {
        t.team_name.strip(): [(p.position, float(pool.get(p.name, 0.0))) for p in t.roster]
        for t in teams
    }
    return (
        league_positional_strength(points_rosters, requirements, bench_weight),
        league_positional_strength(value_rosters, requirements, bench_weight),
    )


def _ordered_positions(strength: LeagueStrength) -> list[str]:
    present = set(strength.positions)
    return [p for p in POSITION_ORDER if p in present] + sorted(present - set(POSITION_ORDER))


def _cell(standing: TeamPositionStanding | None) -> str:
    if standing is None:
        return f"{'-':>9} {'-':>6} {'-':>7}  "
    rank = f"{standing.rank}/{standing.team_count}"
    return f"{standing.strength:>9.1f} {rank:>6} {standing.z:>+7.2f}  "


def _header(metric: str) -> str:
    head = f"{'POS':<6}"
    if metric in ("points", "both"):
        head += f"{'Points':>9} {'rank':>6} {'z':>7}  "
    if metric in ("value", "both"):
        head += f"{'Value':>9} {'rank':>6} {'z':>7}  "
    return head + "verdict"


def _render_team(points: LeagueStrength, value: LeagueStrength, team_name: str, metric: str) -> str:
    lines = [
        f"Positional strength — {team_name}   (league of {points.team_count})",
        "",
        _header(metric),
    ]
    for position in _ordered_positions(points):
        ps = points.standing(team_name, position)
        row = f"{position:<6}"
        if metric in ("points", "both"):
            row += _cell(ps)
        if metric in ("value", "both"):
            row += _cell(value.standing(team_name, position))
        row += classify_strength(ps.z) if ps is not None else ""
        lines.append(row.rstrip())

    weak = [
        f"{position} (z {z:+.2f})" for position, z in points.weak_spots(team_name) if z <= WEAK_Z
    ]
    if weak:
        lines += ["", "Weak spots (points ruler): " + ", ".join(weak)]
    return "\n".join(lines)


def _render_all(
    points: LeagueStrength, value: LeagueStrength, marked_team: str | None, metric: str
) -> str:
    lines = [f"Positional strength — all teams   (league of {points.team_count})", ""]
    for position in _ordered_positions(points):
        lines.append(position)
        standings = points.positions[position].standings
        for name in sorted(standings, key=lambda n: standings[n].strength, reverse=True):
            marker = "*" if name == marked_team else " "
            row = f"  {marker}{name:<24}"
            if metric in ("points", "both"):
                row += _cell(standings[name])
            if metric in ("value", "both"):
                row += _cell(value.standing(name, position))
            lines.append(row.rstrip())
        lines.append("")
    return "\n".join(lines).rstrip()


def main():
    parser = argparse.ArgumentParser(description="Empire League positional strength")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report_parser = subparsers.add_parser("report", help="Show positional strength vs the league")
    report_parser.add_argument(
        "--team", help="ESPN team name (defaults to my_team_name in config.yaml)"
    )
    report_parser.add_argument(
        "--all", action="store_true", help="Show every team, not just --team"
    )
    report_parser.add_argument(
        "--metric",
        choices=("points", "value", "both"),
        default="both",
        help="Which ruler(s) to show (default: both)",
    )

    args = parser.parse_args()
    config = load_config()
    league = espn_client.get_league(config)

    if args.command == "report":
        points, value = build_strengths(config, league)

        marked = None
        team_name = args.team or config.get("my_team_name")
        if team_name:
            try:
                marked = find_team(league, team_name).team_name.strip()
            except RuntimeError as e:
                parser.error(str(e))

        if args.all:
            print(_render_all(points, value, marked, args.metric))
        elif marked:
            print(_render_team(points, value, marked, args.metric))
        else:
            parser.error("No team specified. Pass --team or set my_team_name in config.yaml.")


if __name__ == "__main__":
    main()
