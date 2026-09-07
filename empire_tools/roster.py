"""Roster construction shared by the auction and FAAB tools: how many of
each slot type a manager must fill, and figuring out what's still needed
from a manager's currently rostered positions.
"""

from dataclasses import dataclass

# espn_api slot labels that represent a flex spot (accept more than one
# base position) vs a true single-position bench spot. 'D/ST' contains a
# slash too but is a single position (defense/special teams), not a flex.
FLEX_LABELS = {"RB/WR", "WR/TE", "RB/WR/TE", "OP"}
BENCH_LABELS = {"BE"}
# IR slots are roster capacity but not something you draft or bid into: they
# only hold players already rostered elsewhere who've been ruled out. Kept
# separate so they don't inflate `total_spots` (and with it the auction's
# $1-per-remaining-spot max-bid reserve) or bench progress readouts.
IR_LABELS = {"IR"}


@dataclass
class RosterRequirements:
    """How many of each roster slot type a manager must fill.

    `starters` is keyed by base position (e.g. "QB", "RB", "D/ST"). Flex
    slots are pooled into a single `flex_spots` bucket with the union of
    positions eligible across whatever flex slot types are configured -
    an approximation, but standard leagues (this one included) only run one
    flex type, so it's exact in the common case.
    """

    starters: dict[str, int]
    flex_spots: int = 0
    flex_eligible: frozenset[str] = frozenset()
    bench_spots: int = 0
    # Informational only - IR slots aren't drafted into, so they're excluded
    # from `total_spots` and every draft/bid calculation built on it.
    ir_spots: int = 0

    @property
    def total_spots(self) -> int:
        return sum(self.starters.values()) + self.flex_spots + self.bench_spots


def requirements_from_espn_slot_counts(position_slot_counts: dict[str, int]) -> RosterRequirements:
    """Translate espn_api's League.settings.position_slot_counts into a RosterRequirements."""
    starters: dict[str, int] = {}
    flex_spots = 0
    flex_eligible: set[str] = set()
    bench_spots = 0
    ir_spots = 0

    for slot, count in position_slot_counts.items():
        if count <= 0:
            continue
        if slot in FLEX_LABELS:
            flex_spots += count
            flex_eligible |= {"QB", "RB", "WR", "TE"} if slot == "OP" else set(slot.split("/"))
        elif slot in BENCH_LABELS:
            bench_spots += count
        elif slot in IR_LABELS:
            ir_spots += count
        else:
            starters[slot] = count

    return RosterRequirements(
        starters=starters,
        flex_spots=flex_spots,
        flex_eligible=frozenset(flex_eligible),
        bench_spots=bench_spots,
        ir_spots=ir_spots,
    )


def find_team(league, team_name: str):
    """Look up a team by exact name, tolerating the stray leading/trailing
    whitespace ESPN sometimes carries in `Team.team_name` (e.g.
    ``"Burms Burners "``). Raises `RuntimeError` if there's no match. Shared
    by the FAAB and trade tools, which both take a team name off the CLI."""
    target = team_name.strip()
    team = next((t for t in league.teams if t.team_name.strip() == target), None)
    if team is None:
        raise RuntimeError(f"No team named {team_name!r} in this league.")
    return team


def needed_positions(requirements: RosterRequirements, rostered_positions: list[str]) -> set[str]:
    """Positions that would still fill an open starting/flex slot, given the
    base positions of players already on a roster. Greedily assigns each
    rostered player to the most specific open slot (exact position, then
    flex) - the same fill order the auction draft uses - since bench
    overflow doesn't change what's still needed."""
    starters_remaining = dict(requirements.starters)
    flex_remaining = requirements.flex_spots

    for position in rostered_positions:
        if starters_remaining.get(position, 0) > 0:
            starters_remaining[position] -= 1
        elif position in requirements.flex_eligible and flex_remaining > 0:
            flex_remaining -= 1

    needed = {pos for pos, left in starters_remaining.items() if left > 0}
    if flex_remaining > 0:
        needed |= requirements.flex_eligible
    return needed
