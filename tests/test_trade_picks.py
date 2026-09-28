import pytest

from empire_tools.trade.evaluate import SideNeeds, SidePlayer, evaluate_trade
from empire_tools.trade.picks import (
    PICK_POSITION,
    PickSpec,
    parse_pick,
    pick_value,
    rookie_slot_values,
    year_multiplier,
)

# 10-team, 2-round toy league: 20 slots, rookie values 200, 190, ..., 10.
LEAGUE = 10
ROUNDS = 2
YEAR = 2026
POOL = {f"R{i}": 200.0 - 10 * i for i in range(20)}
SLOTS = rookie_slot_values(list(POOL), POOL, LEAGUE, ROUNDS)


# --- parse_pick ------------------------------------------------------------


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("2027:2", PickSpec(2027, 2)),
        ("2027:1:late", PickSpec(2027, 1, tier="late")),
        ("2028:1:EARLY", PickSpec(2028, 1, tier="early")),
        ("2027:1:4", PickSpec(2027, 1, slot=4)),
    ],
)
def test_parse_pick_accepts_round_tier_and_slot(spec, expected):
    assert parse_pick(spec, LEAGUE, ROUNDS, YEAR) == expected


@pytest.mark.parametrize(
    "spec",
    ["2027", "2027:1:2:3", "next:1", "2026:1", "2025:1", "2027:0", "2027:3", "2027:1:0", "2027:1:11", "2027:1:soon"],
)
def test_parse_pick_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        parse_pick(spec, LEAGUE, ROUNDS, YEAR)


def test_pick_labels():
    assert PickSpec(2027, 1, slot=4).label == "2027 R1 (1.04)"
    assert PickSpec(2027, 2, tier="late").label == "2027 R2 (late)"
    assert PickSpec(2027, 2).label == "2027 R2"


# --- rookie_slot_values ---------------------------------------------------


def test_slot_values_sort_by_value_not_list_order():
    pool = {"a": 5.0, "b": 50.0, "c": 20.0}
    assert rookie_slot_values(["a", "b", "c"], pool, 2, 2) == [50.0, 20.0, 5.0, 0.0]


def test_slot_values_pad_truncate_and_ignore_missing_and_duplicates():
    pool = {"a": 5.0, "b": 50.0}
    assert rookie_slot_values(["a", "b", "b", "ghost"], pool, 2, 2) == [50.0, 5.0, 0.0, 0.0]
    assert rookie_slot_values(list(POOL), POOL, 2, 2) == [200.0, 190.0, 180.0, 170.0]


# --- pick_value --------------------------------------------------------------


def test_next_year_slot_value_takes_one_year_of_discount():
    assert pick_value(PickSpec(2027, 1, slot=1), SLOTS, LEAGUE, YEAR, 0.15) == pytest.approx(200 * 0.85)
    assert pick_value(PickSpec(2027, 2, slot=10), SLOTS, LEAGUE, YEAR, 0.0) == pytest.approx(10.0)


def test_tiers_split_a_10_team_round_3_4_3():
    early = pick_value(PickSpec(2027, 1, tier="early"), SLOTS, LEAGUE, YEAR, 0.0)
    mid = pick_value(PickSpec(2027, 1, tier="mid"), SLOTS, LEAGUE, YEAR, 0.0)
    late = pick_value(PickSpec(2027, 1, tier="late"), SLOTS, LEAGUE, YEAR, 0.0)
    assert early == pytest.approx((200 + 190 + 180) / 3)
    assert mid == pytest.approx((170 + 160 + 150 + 140) / 4)
    assert late == pytest.approx((130 + 120 + 110) / 3)


def test_unknown_slot_is_round_average():
    assert pick_value(PickSpec(2027, 2), SLOTS, LEAGUE, YEAR, 0.0) == pytest.approx(55.0)


def test_further_out_picks_compound_the_discount():
    assert year_multiplier(2028, YEAR, 0.15) == pytest.approx(0.85**2)
    one = pick_value(PickSpec(2027, 1, slot=1), SLOTS, LEAGUE, YEAR, 0.15)
    two = pick_value(PickSpec(2028, 1, slot=1), SLOTS, LEAGUE, YEAR, 0.15)
    assert two == pytest.approx(one * 0.85)


def test_tiny_league_mid_tier_falls_back_to_round():
    slots = rookie_slot_values(["a", "b"], {"a": 10.0, "b": 4.0}, 2, 1)
    assert pick_value(PickSpec(2027, 1, tier="mid"), slots, 2, YEAR, 0.0) == pytest.approx(7.0)


# --- picks inside a trade ----------------------------------------------------


def test_pick_moves_long_term_grade_but_not_ros():
    pick = SidePlayer(name="2027 R1", position=PICK_POSITION, ros_value=0.0, lt_value=100.0)
    player = SidePlayer(name="QB", position="QB", ros_value=200.0, lt_value=100.0)
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[player, pick],
        user_given=[SidePlayer(name="Mine", position="QB", ros_value=200.0, lt_value=100.0)],
        user_needs=SideNeeds(),
        counterparty_needs=SideNeeds(),
    )
    assert result.user.ros.raw_value_in == pytest.approx(200.0)
    assert result.user.long_term.raw_value_in == pytest.approx(200.0)
    assert result.user.long_term.grade == "A"
