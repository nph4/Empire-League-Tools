"""Value-based tiering: grouping players at a position into draft-day tiers
by where the real talent drop-offs are, rather than by fixed rank buckets.

A new tier starts wherever the value gap to the next-best player is large
relative to that player's own value - the drop from a $60 player to a $45
player (25%) is a much bigger signal than the same $15 drop from a $200
player to a $185 player (7.5%), so the threshold is relative, not absolute.
"""

from typing import Iterable, Protocol


class HasNameAndPosition(Protocol):
    name: str
    position: str


def assign_tiers(sorted_values: list[float], gap_threshold: float) -> list[int]:
    """Assign a 1-indexed tier number to each value in `sorted_values`
    (must be sorted descending). A new tier starts whenever the drop from
    the previous value exceeds `gap_threshold` as a fraction of the
    previous value."""
    tiers: list[int] = []
    tier = 1
    previous: float | None = None

    for value in sorted_values:
        if previous is not None and previous > 0 and (previous - value) / previous > gap_threshold:
            tier += 1
        tiers.append(tier)
        previous = value

    return tiers


def assign_tiers_by_position(
    value_pool: dict[str, float], players: Iterable[HasNameAndPosition], gap_threshold: float
) -> dict[str, int]:
    """Tier every player in `players`, independently per position (a tier 1
    QB and a tier 1 RB aren't held to the same bar)."""
    by_position: dict[str, list[HasNameAndPosition]] = {}
    for player in players:
        by_position.setdefault(player.position, []).append(player)

    result: dict[str, int] = {}
    for position_players in by_position.values():
        ranked = sorted(position_players, key=lambda p: value_pool.get(p.name, 0), reverse=True)
        tiers = assign_tiers([value_pool.get(p.name, 0) for p in ranked], gap_threshold)
        for player, tier in zip(ranked, tiers):
            result[player.name] = tier

    return result
