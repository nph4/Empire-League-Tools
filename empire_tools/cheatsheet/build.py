"""Combines player value (valuations.py), computed tiers (tiers.py), and the
hand-maintained overlay (notes.py) into the rows a cheat sheet renders."""

from dataclasses import dataclass
from typing import Iterable, Protocol

from empire_tools.cheatsheet.notes import PlayerNotes
from empire_tools.cheatsheet.tiers import assign_tiers_by_position

# injuryStatus values espn_api reports when a player isn't just healthy.
_HEALTHY_STATUSES = {None, "ACTIVE"}


class HasNamePositionTeamAndInjury(Protocol):
    name: str
    position: str
    proTeam: str
    injuryStatus: str | None


@dataclass
class CheatSheetRow:
    name: str
    position: str
    pro_team: str
    value: float
    tier: int
    flags: list[str]
    notes: str


def build_rows(
    players: Iterable[HasNamePositionTeamAndInjury],
    value_pool: dict[str, float],
    notes: dict[str, PlayerNotes],
    gap_threshold: float,
) -> list[CheatSheetRow]:
    players = list(players)
    auto_tiers = assign_tiers_by_position(value_pool, players, gap_threshold)

    rows = []
    for player in players:
        player_notes = notes.get(player.name, PlayerNotes())

        flags = []
        if getattr(player, "injuryStatus", None) not in _HEALTHY_STATUSES:
            flags.append(player.injuryStatus)
        for flag in player_notes.flags:
            if flag not in flags:
                flags.append(flag)

        rows.append(
            CheatSheetRow(
                name=player.name,
                position=player.position,
                pro_team=player.proTeam,
                value=value_pool.get(player.name, 0),
                tier=player_notes.tier_override or auto_tiers.get(player.name, 1),
                flags=flags,
                notes=player_notes.notes,
            )
        )

    rows.sort(key=lambda r: (r.position, r.tier, -r.value))
    return rows
