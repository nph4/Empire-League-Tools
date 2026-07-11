"""Live bid/target suggestions for the auction assistant.

The model: each player's baseline value (see `valuations.py`) is a relative
score, not a dollar amount. At any point in the draft, a player's suggested
price is their share of *remaining* spendable dollars, proportional to their
share of the *remaining* pool's total value:

    suggested_bid(player) = 1 + (player_value / remaining_pool_value) * remaining_spendable

`remaining_spendable` is total remaining manager budgets minus $1 reserved
per remaining roster spot (every player costs at least $1). Recomputing this
ratio fresh against current state — rather than tracking a separate
"inflation" multiplier — means inflation/deflation from real bidding falls
out automatically: as dollars get spent above or below a player's relative
share, the remaining pool's price-per-value shifts for everyone left.
"""

from empire_tools.auction.state import DraftState


def _remaining_spendable(state: DraftState) -> int:
    remaining_budget = sum(m.remaining for m in state.managers.values())
    remaining_spots = sum(
        state.roster_spots_per_manager - m.roster_size for m in state.managers.values()
    )
    return remaining_budget - remaining_spots


def suggest_bid(state: DraftState, value_pool: dict[str, float], player_name: str) -> int:
    """Return a suggested max bid for `player_name` given current draft state."""
    if player_name not in state.available:
        raise KeyError(f"{player_name!r} is not in the available player pool")

    remaining_pool_value = sum(
        value_pool.get(name, 0) for name in state.available
    ) or 1
    player_value = value_pool.get(player_name, 0)

    suggested = 1 + (player_value / remaining_pool_value) * _remaining_spendable(state)
    return round(suggested)


def suggest_targets(
    state: DraftState, value_pool: dict[str, float], manager_name: str, count: int = 5
) -> list[tuple[str, int]]:
    """Return up to `count` available (player, suggested_bid) pairs that
    `manager_name` can currently afford, best value first."""
    max_bid = state.max_bid(manager_name)

    affordable = []
    for player_name in state.available:
        bid = suggest_bid(state, value_pool, player_name)
        if bid <= max_bid:
            affordable.append((player_name, bid))

    affordable.sort(key=lambda pair: pair[1], reverse=True)
    return affordable[:count]
