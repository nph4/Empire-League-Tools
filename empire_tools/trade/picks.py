"""Future rookie-draft picks as trade assets: pure logic, no ESPN or I/O.

A pick has no ESPN projection and no row in the dynasty rankings, so it's
priced by proxy: **a future pick is worth what the same slot in the most
recent rookie class is worth today.** The configured rookie-class list
(`trade.rookie_class_csv`) names that class; each rookie's value is looked up
in the same dynasty value pool the rest of the trade uses (so picks and
players share one scale), sorted high-to-low, and cut into rounds of
`league_size` picks. Slots past the end of the list are worth 0.

A pick is then either an exact slot (``2027:1:4`` -> 1.04), a third of a
round (``early`` / ``mid`` / ``late``, averaged), or - when the owner's
finish is unknown - the whole round's average (``2027:2``). Each year out
past the current season multiplies the value by ``1 - year_discount``:
this year's rookie values already include post-draft hype a pick hasn't
earned, and a further-out pick is further from helping.

Picks carry zero rest-of-season value (a future rookie doesn't score this
year) and never take a roster spot.
"""

from dataclasses import dataclass

DEFAULT_ROOKIE_DRAFT_ROUNDS = 4
DEFAULT_PICK_YEAR_DISCOUNT = 0.15

PICK_POSITION = "PICK"

TIERS = ("early", "mid", "late")


@dataclass(frozen=True)
class PickSpec:
    year: int
    round: int
    slot: int | None = None  # 1-based within the round
    tier: str | None = None  # "early" | "mid" | "late"

    @property
    def label(self) -> str:
        base = f"{self.year} R{self.round}"
        if self.slot is not None:
            return f"{base} ({self.round}.{self.slot:02d})"
        if self.tier is not None:
            return f"{base} ({self.tier})"
        return base


def parse_pick(spec: str, league_size: int, rounds: int, current_year: int) -> PickSpec:
    """Parse ``YEAR:ROUND[:SLOT|early|mid|late]``. Raises ValueError with a
    user-facing message on anything malformed or out of range."""
    parts = spec.strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"{spec!r}: expected YEAR:ROUND or YEAR:ROUND:(SLOT|early|mid|late).")
    try:
        year, rnd = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"{spec!r}: year and round must be whole numbers.") from None

    if year <= current_year:
        raise ValueError(f"{spec!r}: the {year} rookie draft isn't a future pick (current season {current_year}).")
    if not 1 <= rnd <= rounds:
        raise ValueError(f"{spec!r}: round must be 1-{rounds}.")

    if len(parts) == 2:
        return PickSpec(year, rnd)

    where = parts[2].strip().lower()
    if where in TIERS:
        return PickSpec(year, rnd, tier=where)
    try:
        slot = int(where)
    except ValueError:
        raise ValueError(f"{spec!r}: third part must be a slot number or one of {', '.join(TIERS)}.") from None
    if not 1 <= slot <= league_size:
        raise ValueError(f"{spec!r}: slot must be 1-{league_size}.")
    return PickSpec(year, rnd, slot=slot)


def rookie_slot_values(
    rookie_names: list[str], value_pool: dict[str, float], league_size: int, rounds: int
) -> list[float]:
    """Value of every draft slot, overall pick order (index 0 = 1.01),
    `league_size * rounds` long. Rookies missing from the pool count as 0."""
    values = sorted((value_pool.get(name, 0.0) for name in dict.fromkeys(rookie_names)), reverse=True)
    total = league_size * rounds
    return (values + [0.0] * total)[:total]


def _tier_bounds(tier: str, league_size: int) -> tuple[int, int]:
    """0-based [start, end) within a round. Thirds, with any remainder in
    the middle: 10 teams -> 3 / 4 / 3, 12 -> 4 / 4 / 4."""
    edge = max(1, league_size // 3)
    if tier == "early":
        return 0, edge
    if tier == "late":
        return league_size - edge, league_size
    return edge, league_size - edge


def year_multiplier(year: int, current_year: int, year_discount: float) -> float:
    return (1.0 - year_discount) ** max(0, year - current_year)


def pick_value(
    pick: PickSpec,
    slot_values: list[float],
    league_size: int,
    current_year: int,
    year_discount: float = DEFAULT_PICK_YEAR_DISCOUNT,
) -> float:
    """Dynasty value of `pick` on the value-pool scale, discounted by year."""
    round_values = slot_values[(pick.round - 1) * league_size : pick.round * league_size]
    if pick.slot is not None:
        base = round_values[pick.slot - 1]
    else:
        start, end = _tier_bounds(pick.tier, league_size) if pick.tier else (0, league_size)
        chunk = round_values[start:end] or round_values  # tiny leagues: no distinct middle
        base = sum(chunk) / len(chunk)
    return base * year_multiplier(pick.year, current_year, year_discount)
