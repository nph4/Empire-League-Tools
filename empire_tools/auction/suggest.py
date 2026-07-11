"""Bid suggestion logic for the live auction assistant.

This is the extension point for the actual "smarts" of the draft
assistant. Nothing here is implemented yet — plug in player valuations,
positional scarcity, and manager tendencies as they get built out.
"""

from empire_tools.auction.state import DraftState


def suggest_bid(state: DraftState, player_name: str) -> int:
    """Return a suggested max bid for `player_name`.

    TODO: incorporate player value/ranking data, positional scarcity
    among remaining available players, and league-wide remaining budget.
    """
    raise NotImplementedError("Bid valuation model not implemented yet")


def suggest_targets(state: DraftState, manager_name: str, count: int = 5) -> list[str]:
    """Return the top `count` available players worth bidding on for
    `manager_name` right now.

    TODO: rank `state.available` by value relative to remaining budget
    and roster needs.
    """
    raise NotImplementedError("Target suggestion model not implemented yet")
