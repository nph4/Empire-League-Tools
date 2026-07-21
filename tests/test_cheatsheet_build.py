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


def test_non_string_injury_status_from_espn_is_treated_as_healthy():
    # espn_api reports [] instead of a string/None for some inactive players
    row = build_rows([FakePlayer("Retired Guy", "WR", "KC", injuryStatus=[])], {"Retired Guy": 50.0}, {}, gap_threshold=0.15)[0]
    assert row.flags == []


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


def test_window_fit_multiplier_adjusts_value_and_flags_the_change():
    notes = {"Aging Vet": PlayerNotes(window_fit_multiplier=0.8)}
    row = build_rows([FakePlayer("Aging Vet", "RB", "KC")], {"Aging Vet": 50.0}, notes, gap_threshold=0.15)[0]

    assert row.value == 40.0
    assert "window×0.8" in row.flags


def test_neutral_window_fit_multiplier_adds_no_flag():
    notes = {"Some Player": PlayerNotes(window_fit_multiplier=1.0)}
    row = build_rows([FakePlayer("Some Player", "RB", "KC")], {"Some Player": 50.0}, notes, gap_threshold=0.15)[0]
    assert row.flags == []


def test_window_fit_multiplier_can_move_a_player_between_tiers():
    players = [FakePlayer("Top", "RB", "KC"), FakePlayer("Faded Vet", "RB", "KC")]
    value_pool = {"Top": 100.0, "Faded Vet": 95.0}
    # without the downgrade these two would land in the same tier (only a 5% gap)
    notes = {"Faded Vet": PlayerNotes(window_fit_multiplier=0.5)}

    rows = {r.name: r for r in build_rows(players, value_pool, notes, gap_threshold=0.15)}

    assert rows["Top"].tier == 1
    assert rows["Faded Vet"].tier == 2


def test_team_bias_flag_applied_from_config():
    row = build_rows(
        [FakePlayer("Vikings Guy", "WR", "MIN")],
        {"Vikings Guy": 50.0},
        {},
        gap_threshold=0.15,
        team_bias_flags={"MIN": "MN-bias"},
    )[0]
    assert "MN-bias" in row.flags


def test_team_bias_flag_omitted_for_unmapped_team():
    row = build_rows(
        [FakePlayer("Some Guy", "WR", "DAL")],
        {"Some Guy": 50.0},
        {},
        gap_threshold=0.15,
        team_bias_flags={"MIN": "MN-bias"},
    )[0]
    assert row.flags == []


def test_mid_tier_te_gets_flagged():
    players = [FakePlayer(f"TE {i}", "TE", "KC") for i in range(3)]
    # three well-separated tiers: 1, 2, 3
    value_pool = {"TE 0": 100.0, "TE 1": 50.0, "TE 2": 10.0}

    rows = {r.name: r for r in build_rows(players, value_pool, {}, gap_threshold=0.15)}

    assert "mid-tier-TE" not in rows["TE 0"].flags  # tier 1 (elite)
    assert "mid-tier-TE" in rows["TE 1"].flags  # tier 2 (the middle to avoid)
    assert "mid-tier-TE" not in rows["TE 2"].flags  # tier 3 (last/waiver tier)


def test_mid_tier_te_flag_never_fires_for_non_te_positions():
    players = [FakePlayer(f"RB {i}", "RB", "KC") for i in range(3)]
    value_pool = {"RB 0": 100.0, "RB 1": 50.0, "RB 2": 10.0}

    rows = build_rows(players, value_pool, {}, gap_threshold=0.15)

    assert all("mid-tier-TE" not in row.flags for row in rows)


def test_mid_tier_te_flag_does_not_fire_with_only_two_tiers():
    players = [FakePlayer("TE Top", "TE", "KC"), FakePlayer("TE Bottom", "TE", "KC")]
    value_pool = {"TE Top": 100.0, "TE Bottom": 10.0}

    rows = build_rows(players, value_pool, {}, gap_threshold=0.15)

    assert all("mid-tier-TE" not in row.flags for row in rows)
