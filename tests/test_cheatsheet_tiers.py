from dataclasses import dataclass

from empire_tools.cheatsheet.tiers import assign_tiers, assign_tiers_by_position


def test_no_gap_keeps_everyone_in_one_tier():
    assert assign_tiers([100.0, 95.0, 90.0], gap_threshold=0.15) == [1, 1, 1]


def test_large_relative_drop_starts_a_new_tier():
    # 100 -> 70 is a 30% drop, above the 15% threshold
    assert assign_tiers([100.0, 70.0, 65.0], gap_threshold=0.15) == [1, 2, 2]


def test_multiple_gaps_produce_multiple_tiers():
    assert assign_tiers([100.0, 60.0, 20.0], gap_threshold=0.15) == [1, 2, 3]


def test_empty_list_returns_empty():
    assert assign_tiers([], gap_threshold=0.15) == []


def test_single_value_is_tier_one():
    assert assign_tiers([42.0], gap_threshold=0.15) == [1]


@dataclass
class FakePlayer:
    name: str
    position: str


def test_tiers_are_computed_independently_per_position():
    value_pool = {"Top QB": 100.0, "Bad QB": 10.0, "Top RB": 50.0, "Also Top RB": 48.0}
    players = [
        FakePlayer("Top QB", "QB"),
        FakePlayer("Bad QB", "QB"),
        FakePlayer("Top RB", "RB"),
        FakePlayer("Also Top RB", "RB"),
    ]

    tiers = assign_tiers_by_position(value_pool, players, gap_threshold=0.15)

    assert tiers["Top QB"] == 1
    assert tiers["Bad QB"] == 2
    # a huge RB1/RB2 gap elsewhere shouldn't push these two close RBs apart
    assert tiers["Top RB"] == tiers["Also Top RB"] == 1


def test_lone_player_at_a_position_is_tier_one():
    value_pool = {"Only TE": 20.0}
    tiers = assign_tiers_by_position(value_pool, [FakePlayer("Only TE", "TE")], gap_threshold=0.15)
    assert tiers["Only TE"] == 1
