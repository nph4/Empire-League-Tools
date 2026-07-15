from dataclasses import dataclass

from empire_tools.cheatsheet.build import build_rows
from empire_tools.cheatsheet.notes import PlayerNotes


@dataclass
class FakePlayer:
    name: str
    position: str
    proTeam: str
    injuryStatus: str | None = "ACTIVE"


def test_healthy_player_gets_no_auto_flag():
    row = build_rows([FakePlayer("Healthy Guy", "RB", "KC")], {"Healthy Guy": 50.0}, {}, gap_threshold=0.15)[0]
    assert row.flags == []


def test_injured_player_gets_an_auto_flag_from_espn():
    row = build_rows(
        [FakePlayer("Hurt Guy", "RB", "KC", injuryStatus="QUESTIONABLE")], {"Hurt Guy": 50.0}, {}, gap_threshold=0.15
    )[0]
    assert row.flags == ["QUESTIONABLE"]


def test_manual_flags_merge_with_auto_flag_without_duplicates():
    notes = {"Hurt Guy": PlayerNotes(flags=["camp-riser", "QUESTIONABLE"])}
    row = build_rows(
        [FakePlayer("Hurt Guy", "RB", "KC", injuryStatus="QUESTIONABLE")], {"Hurt Guy": 50.0}, notes, gap_threshold=0.15
    )[0]
    assert row.flags == ["QUESTIONABLE", "camp-riser"]


def test_tier_override_wins_over_auto_tier():
    players = [FakePlayer("Star", "WR", "DAL"), FakePlayer("Backup", "WR", "DAL")]
    value_pool = {"Star": 100.0, "Backup": 10.0}
    notes = {"Backup": PlayerNotes(tier_override=1)}

    rows = {r.name: r for r in build_rows(players, value_pool, notes, gap_threshold=0.15)}

    assert rows["Star"].tier == 1
    assert rows["Backup"].tier == 1  # would otherwise be tier 2 from the big value gap


def test_rows_sort_by_position_then_tier_then_value_descending():
    players = [
        FakePlayer("RB Two", "RB", "KC"),
        FakePlayer("QB One", "QB", "BUF"),
        FakePlayer("RB One", "RB", "KC"),
    ]
    value_pool = {"RB Two": 40.0, "QB One": 90.0, "RB One": 80.0}

    rows = build_rows(players, value_pool, {}, gap_threshold=0.15)

    assert [r.name for r in rows] == ["QB One", "RB One", "RB Two"]


def test_missing_value_defaults_to_zero_not_a_crash():
    row = build_rows([FakePlayer("Unranked", "TE", "SF")], {}, {}, gap_threshold=0.15)[0]
    assert row.value == 0
