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
    team_bias_flags: dict[str, str] | None = None,
) -> list[CheatSheetRow]:
    players = list(players)
    team_bias_flags = team_bias_flags or {}

    # window_fit_multiplier lets a hand-entered win-timing call actually
    # move a player's rank (not just be a footnote) - fold it in before
    # tiering, since there's no ESPN-sourced signal to compute this
    # automatically (see notes.py's PlayerNotes.window_fit_multiplier).
    effective_values = {
        player.name: value_pool.get(player.name, 0) * notes.get(player.name, PlayerNotes()).window_fit_multiplier
        for player in players
    }
    auto_tiers = assign_tiers_by_position(effective_values, players, gap_threshold)
    max_te_tier = max((auto_tiers[p.name] for p in players if p.position == "TE"), default=1)

    rows = []
    for player in players:
        player_notes = notes.get(player.name, PlayerNotes())
        tier = player_notes.tier_override or auto_tiers.get(player.name, 1)

        flags = []
        injury_status = getattr(player, "injuryStatus", None)
        # espn_api returns [] rather than None for some inactive/off-roster
        # players (e.g. retired vets still in ESPN's player pool) - treat
        # anything that isn't an actual status string as no-data/healthy.
        if not isinstance(injury_status, str):
            injury_status = None
        if injury_status not in _HEALTHY_STATUSES:
            flags.append(injury_status)
        if player.proTeam in team_bias_flags:
            flags.append(team_bias_flags[player.proTeam])
        # First TE or last TE, skip the middle - see feedback-te-draft-philosophy memory.
        if player.position == "TE" and 1 < tier < max_te_tier:
            flags.append("mid-tier-TE")
        if player_notes.window_fit_multiplier != 1.0:
            flags.append(f"window×{player_notes.window_fit_multiplier:g}")
        for flag in player_notes.flags:
            if flag not in flags:
                flags.append(flag)

        rows.append(
            CheatSheetRow(
                name=player.name,
                position=player.position,
                pro_team=player.proTeam,
                value=effective_values[player.name],
                tier=tier,
                flags=flags,
                notes=player_notes.notes,
            )
        )

    rows.sort(key=lambda r: (r.position, r.tier, -r.value))
    return rows
