"""League-relative positional strength: pure logic, no ESPN or I/O
dependency (so it's directly unit-testable, like `trade/evaluate.py` and
`auction/state.py`).

`roster.needed_positions()` answers a binary question - "is there an open
starting/flex slot this position could go into?". This module answers a
graded one: *how strong is a team's corps at a position compared to the
rest of the league?* A team can have every slot nominally filled and still
be the league's weakest at running back; that's the signal here.

Corps strength is a **blend**: the players actually manning a position's
starting/flex slots count at full weight, the rest (bench depth) at
`bench_depth_weight` - the same idea as `faab.bench_only_discount`. Which
players are "starters" is decided by value (best players into the slots),
mirroring the most-specific-slot-first fill order of `needed_positions`.
Each player lands in exactly one bucket, so a flex slot's value is credited
once, to the position of whoever currently holds it.

Per position the league's per-team strengths become a mean, a population
standard deviation, a per-team z-score, and a rank (1 = strongest). The
z-score feeds two things: a plain strong/average/weak verdict for the
`strength` report, and - via `weakness_multiplier` - the trade evaluator's
rest-of-season need nudge, replacing its old in-a-set/not-in-a-set
multiplier with a continuous one centred on 1.0 at league average.
"""

from dataclasses import dataclass, field
import statistics

from empire_tools.roster import RosterRequirements

# Weight on players beyond a position's starting/flex slots when scoring
# corps strength. Deliberately the same default as `faab.bench_only_discount`
# - a likely-to-sit stash is real depth but not a starter.
DEFAULT_BENCH_DEPTH_WEIGHT = 0.4

# How many standard deviations below the league mean a corps has to be for a
# received player there to earn the full `need_boost` in the trade nudge
# (and how far above for the full `depth_discount`). Small leagues (10-12
# teams) compress z-scores and one stud swings a position's mean, so this
# sits well under 2. Overridable via `strength.trade_z_span`.
DEFAULT_TRADE_Z_SPAN = 1.5

# Verdict thresholds for the `strength` report, in z-score terms.
WEAK_Z = -0.75
STRONG_Z = 0.75

_EPS = 1e-9


@dataclass(frozen=True)
class TeamPositionStanding:
    """One team's standing at one position. `rank` is 1 = strongest
    (highest `strength`); ties share a rank."""

    strength: float
    z: float
    rank: int
    team_count: int


@dataclass
class PositionLeagueStats:
    position: str
    mean: float
    stdev: float  # population stdev (statistics.pstdev); 0.0 for n <= 1
    standings: dict[str, TeamPositionStanding]  # team_name -> standing


@dataclass
class LeagueStrength:
    positions: dict[str, PositionLeagueStats]  # position -> stats
    team_count: int

    def standing(self, team_name: str, position: str) -> TeamPositionStanding | None:
        stats = self.positions.get(position)
        if stats is None:
            return None
        return stats.standings.get(team_name)

    def weak_spots(self, team_name: str, limit: int | None = None) -> list[tuple[str, float]]:
        """`(position, z)` for this team, weakest (most negative z) first."""
        out = [
            (position, stats.standings[team_name].z)
            for position, stats in self.positions.items()
            if team_name in stats.standings
        ]
        out.sort(key=lambda pair: pair[1])
        return out[:limit] if limit is not None else out

    @property
    def is_degenerate(self) -> bool:
        """True when every team's strength is ~0 at every position - e.g.
        deep preseason with all `projected_total_points` still None/0. The
        trade wiring treats this as "no signal" and falls back to the binary
        need nudge."""
        return all(
            abs(standing.strength) < _EPS
            for stats in self.positions.values()
            for standing in stats.standings.values()
        )


def corps_strength_by_position(
    roster: list[tuple[str, float]],
    requirements: RosterRequirements,
    bench_depth_weight: float = DEFAULT_BENCH_DEPTH_WEIGHT,
) -> dict[str, float]:
    """Score one team's corps at each base position.

    `roster` is `(base_position, value)` per rostered player - `value` from
    whichever ruler the caller picked (ESPN projected points or the dynasty
    value pool). Starters/flex count at weight 1.0, everyone else at
    `bench_depth_weight`; best players fill the slots.
    """
    by_pos: dict[str, list[float]] = {}
    for position, value in roster:
        by_pos.setdefault(position, []).append(float(value))
    for values in by_pos.values():
        values.sort(reverse=True)

    strength: dict[str, float] = {}
    flex_candidates: list[tuple[float, str]] = []  # (value, position) - leftovers eligible for flex
    bench: list[tuple[float, str]] = []  # (value, position) - everything past starters + flex

    for position, values in by_pos.items():
        starter_slots = requirements.starters.get(position, 0)
        strength[position] = sum(values[:starter_slots])  # weight 1.0
        for value in values[starter_slots:]:
            if position in requirements.flex_eligible:
                flex_candidates.append((value, position))
            else:
                bench.append((value, position))

    flex_candidates.sort(reverse=True)
    for value, position in flex_candidates[: requirements.flex_spots]:
        strength[position] = strength.get(position, 0.0) + value  # weight 1.0
    bench.extend(flex_candidates[requirements.flex_spots :])

    for value, position in bench:
        strength[position] = strength.get(position, 0.0) + bench_depth_weight * value

    for position in _relevant_positions(requirements, by_pos):
        strength.setdefault(position, 0.0)
    return strength


def _relevant_positions(requirements: RosterRequirements, by_pos: dict[str, list[float]]) -> set[str]:
    return set(requirements.starters) | set(requirements.flex_eligible) | set(by_pos)


def league_positional_strength(
    rosters: dict[str, list[tuple[str, float]]],
    requirements: RosterRequirements,
    bench_depth_weight: float = DEFAULT_BENCH_DEPTH_WEIGHT,
) -> LeagueStrength:
    """Roll per-team corps strengths up into per-position league stats
    (mean, population stdev, per-team z-score and rank)."""
    per_team = {
        name: corps_strength_by_position(roster, requirements, bench_depth_weight)
        for name, roster in rosters.items()
    }
    team_count = len(per_team)
    positions = sorted({position for strengths in per_team.values() for position in strengths})

    stats: dict[str, PositionLeagueStats] = {}
    for position in positions:
        by_team = {name: strengths.get(position, 0.0) for name, strengths in per_team.items()}
        values = list(by_team.values())
        mean = statistics.fmean(values) if values else 0.0
        stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
        standings = {
            name: TeamPositionStanding(
                strength=value,
                z=0.0 if stdev == 0 else (value - mean) / stdev,
                rank=1 + sum(1 for other in values if other > value),
                team_count=team_count,
            )
            for name, value in by_team.items()
        }
        stats[position] = PositionLeagueStats(
            position=position, mean=mean, stdev=stdev, standings=standings
        )
    return LeagueStrength(positions=stats, team_count=team_count)


def classify_strength(z: float) -> str:
    if z <= WEAK_Z:
        return "weak spot"
    if z >= STRONG_Z:
        return "strength"
    return "average"


def weakness_multiplier(
    z: float,
    *,
    need_boost: float,
    depth_discount: float,
    z_span: float = DEFAULT_TRADE_Z_SPAN,
) -> float:
    """Map a corps's league z-score to a trade-nudge multiplier.

    `1.0` at league average (`z == 0`); rises toward `need_boost` as the
    corps gets weaker, falls toward `depth_discount` as it gets stronger;
    bounded in `[depth_discount, need_boost]` and saturating past
    `+/- z_span`. Each side is interpolated independently so `need_boost` /
    `depth_discount` needn't be mirrored about 1.0. `grade_side_model`'s
    `need_swing_cap` clamp stays the final backstop.
    """
    t = max(-1.0, min(1.0, z / z_span)) if z_span else 0.0
    if t <= 0.0:
        return 1.0 + (-t) * (need_boost - 1.0)
    return 1.0 - t * (1.0 - depth_discount)


def team_weakness_multipliers(
    league_strength: LeagueStrength,
    team_name: str,
    *,
    need_boost: float,
    depth_discount: float,
    z_span: float = DEFAULT_TRADE_Z_SPAN,
) -> dict[str, float]:
    """`{position: weakness_multiplier(...)}` for every position this team
    is scored at."""
    return {
        position: weakness_multiplier(
            stats.standings[team_name].z,
            need_boost=need_boost,
            depth_discount=depth_discount,
            z_span=z_span,
        )
        for position, stats in league_strength.positions.items()
        if team_name in stats.standings
    }
