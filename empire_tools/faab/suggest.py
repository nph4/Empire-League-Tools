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
"""

from typing import Iterable, Protocol


class HasNameAndPosition(Protocol):
    name: str
    position: str


def percentile_within_position(
    value_pool: dict[str, float], players: Iterable[HasNameAndPosition], player_name: str
) -> float:
    """1.0 = the best currently-available free agent by value at this
    position, 0.0 = the worst. A lone available player at their position
    is treated as the best available (1.0)."""
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
