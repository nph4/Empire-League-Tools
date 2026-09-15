"""FAAB bid suggestion logic.

Unlike the auction draft, ESPN already tracks real FAAB state for us
(League.settings.acquisition_budget, Team.acquisition_budget_spent) - there's
no need to track manager budgets locally here.

The model: a free agent's suggested bid is a share of your remaining FAAB
budget, driven by how they rank (by baseline value - see valuations.py)
against other free agents currently available at the same position. The
top available player at a position can command a meaningful chunk of
budget; bid size falls off quickly for lesser adds, via a percentile**2
curve - most of a season's FAAB should go to genuine difference-makers,
not incremental depth.

Dynasty CSV rankings (see valuations.py) freeze at Labor Day and never
update again all season, so they can't reflect an in-season breakout or
bust - but ESPN recalculates `projected_total_points` every week off actual
usage. `blend_percentiles` combines a player's dynasty-CSV rank with their
live ESPN rank, weighted toward the live signal as the season progresses
(`live_weight_for_week`) - dynasty rank is still useful context, per
CLAUDE.md, just never enough to out-rank what's actually happening on the
field.
"""

from typing import Iterable, Protocol


class HasNameAndPosition(Protocol):
    name: str
    position: str


class HasInjuryStatus(Protocol):
    injuryStatus: str


INJURY_RESERVE_STATUS = "INJURY_RESERVE"


def is_injury_reserve(player: HasInjuryStatus) -> bool:
    """True if a player is on their NFL team's injured reserve - not merely
    questionable/doubtful/out for a game, but off the 53-man active roster
    and not producing. A dynasty CSV rank can't know this happened after
    Labor Day, so it has to be checked against ESPN's live status rather
    than inferred from value."""
    return getattr(player, "injuryStatus", None) == INJURY_RESERVE_STATUS


def live_weight_for_week(current_week: int, start: float = 0.4, end: float = 0.9, ramp_weeks: int = 8) -> float:
    """How much weight a free agent's blended percentile should give the
    live ESPN signal vs. the preseason dynasty CSV, as the season
    progresses. `start` is the live-signal weight in week 1, when ESPN's
    own projection is still mostly a preseason guess too; it ramps linearly
    to `end` by `ramp_weeks` and holds there - dynasty rank never drops to
    zero weight, since it's still useful context, just never dominant."""
    if ramp_weeks <= 1:
        return end
    progress = min(1.0, max(0.0, (current_week - 1) / (ramp_weeks - 1)))
    return start + (end - start) * progress


def blend_percentiles(dynasty_percentile: float, live_percentile: float, live_weight: float) -> float:
    """Combine a free agent's dynasty-CSV percentile rank at their position
    with their ESPN live-projection percentile rank (both from
    `percentile_within_position`), weighted toward the live signal per
    `live_weight_for_week`."""
    return live_weight * live_percentile + (1 - live_weight) * dynasty_percentile


def percentile_within_position(
    value_pool: dict[str, float], players: Iterable[HasNameAndPosition], player_name: str
) -> float:
    """1.0 = the best currently-available free agent by value at this
    position, 0.0 = the worst. A lone available player at their position
    is treated as the best available (1.0). `value_pool` can be any
    name -> number mapping - a dynasty value pool or a live ESPN projection
    pool - which is what lets `blend_percentiles` combine two independent
    rankings of the same free-agent list."""
    players = list(players)
    position = next(p.position for p in players if p.name == player_name)
    same_position_values = sorted(
        (value_pool.get(p.name, 0) for p in players if p.position == position), reverse=True
    )

    if len(same_position_values) <= 1:
        return 1.0

    rank = same_position_values.index(value_pool.get(player_name, 0))
    return 1 - (rank / (len(same_position_values) - 1))


def suggest_bid(
    remaining_budget: int,
    percentile: float,
    fills_need: bool,
    max_share: float = 0.35,
    bench_only_discount: float = 0.4,
) -> int:
    """Suggested FAAB bid as a share of `remaining_budget`.

    `fills_need` is whether the player would fill an open starting/flex
    slot on your actual current roster (see `empire_tools.roster.needed_positions`).
    Bench-only adds - value notwithstanding - get discounted, since a
    likely-to-sit stash is worth less of your budget than a real starter.
    """
    share = max_share * (percentile**2)
    if not fills_need:
        share *= bench_only_discount
    return round(remaining_budget * share)
