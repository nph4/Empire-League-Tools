import pytest

from empire_tools.trade.evaluate import (
    DEFAULT_NEED_SWING_CAP,
    SideNeeds,
    SidePlayer,
    TradeConfig,
    evaluate_trade,
    fairness_score,
    score_to_grade,
)


def _p(name, position, ros, lt):
    return SidePlayer(name=name, position=position, ros_value=ros, lt_value=lt)


# --- fairness_score -----------------------------------------------------------


def test_fairness_score_even_is_zero():
    assert fairness_score(100, 100) == 0.0


@pytest.mark.parametrize("a,b", [(130, 100), (100, 130), (5, 200), (75, 75), (0, 0)])
def test_fairness_score_is_antisymmetric_between_sides(a, b):
    assert fairness_score(a, b) == pytest.approx(-fairness_score(b, a))


def test_fairness_score_stays_within_minus_one_and_one():
    assert fairness_score(100, 1) == pytest.approx(0.99)
    assert fairness_score(1, 100) == pytest.approx(-0.99)
    # A one-sided giveaway bottoms out at exactly -1.0 (nothing comes back).
    for a, b in [(1000, 1), (1, 1000), (0, 500), (500, 0)]:
        assert -1.0 <= fairness_score(a, b) <= 1.0


# --- score_to_grade ---------------------------------------------------------


@pytest.mark.parametrize(
    "score,grade",
    [
        (0.40, "A"),
        (0.35, "A"),
        (0.30, "B+"),
        (0.20, "B+"),
        (0.15, "B"),
        (0.10, "B"),
        (0.07, "B-"),
        (0.04, "B-"),
        (0.00, "C"),
        (-0.04, "C"),
        (-0.05, "C-"),
        (-0.10, "C-"),
        (-0.15, "D"),
        (-0.20, "D"),
        (-0.30, "D-"),
        (-0.35, "D-"),
        (-0.50, "F"),
        (-1.00, "F"),
    ],
)
def test_score_to_grade_band_edges(score, grade):
    assert score_to_grade(score) == grade


# --- whole-trade behavior -------------------------------------------------------


def test_even_trade_grades_C_for_both_sides():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("Get", "RB", 100, 100)],
        user_given=[_p("Give", "WR", 100, 100)],
        user_needs=SideNeeds(),
        counterparty_needs=SideNeeds(),
    )
    assert result.user.ros.grade == "C"
    assert result.user.long_term.grade == "C"
    assert result.counterparty.ros.grade == "C"
    assert result.counterparty.long_term.grade == "C"


def test_lopsided_trade_raw_scores_mirror_between_sides():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("Get", "RB", 130, 130)],
        user_given=[_p("Give", "RB", 100, 100)],
        user_needs=SideNeeds(),
        counterparty_needs=SideNeeds(),
    )
    assert result.user.ros.raw_score == pytest.approx(-result.counterparty.ros.raw_score)
    assert result.user.ros.score > result.counterparty.ros.score
    assert result.user.long_term.raw_score > 0 > result.counterparty.long_term.raw_score


def test_multi_for_one_is_fair_when_totals_match():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("Stud", "RB", 120, 120)],
        user_given=[
            _p("a", "WR", 40, 40),
            _p("b", "WR", 40, 40),
            _p("c", "WR", 40, 40),
        ],
        user_needs=SideNeeds(),
        counterparty_needs=SideNeeds(),
    )
    # Aggregate value, not player count, drives the grade.
    assert result.user.ros.grade == "C"
    assert result.counterparty.ros.grade == "C"


def test_filling_a_need_lifts_the_ros_grade_but_not_long_term():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("RB1", "RB", 100, 100)],
        user_given=[_p("WR1", "WR", 100, 100)],
        user_needs=SideNeeds(need_before=frozenset({"RB"}), need_after=frozenset()),
        counterparty_needs=SideNeeds(),
    )
    assert result.user.ros.score > result.user.ros.raw_score
    assert result.user.ros.grade != result.user.ros.raw_grade
    # Long-term is a pure value-in vs value-out delta - need never touches it.
    assert result.user.long_term.score == pytest.approx(fairness_score(100, 100))
    assert result.user.long_term.grade == "C"


def test_giving_up_a_player_from_a_thin_spot_dings_the_ros_grade():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("WR1", "WR", 100, 100)],
        user_given=[_p("RB1", "RB", 100, 100)],
        # Nothing needed now, but shipping RB1 out opens an RB hole.
        user_needs=SideNeeds(need_before=frozenset(), need_after=frozenset({"RB"})),
        counterparty_needs=SideNeeds(),
    )
    assert result.user.ros.score < result.user.ros.raw_score


def test_need_nudge_is_clamped_regardless_of_multipliers():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("RB1", "RB", 100, 100)],
        user_given=[_p("WR1", "WR", 100, 100)],
        user_needs=SideNeeds(need_before=frozenset({"RB"}), need_after=frozenset()),
        counterparty_needs=SideNeeds(),
        cfg=TradeConfig(need_boost=5.0, depth_discount=0.01, need_swing_cap=DEFAULT_NEED_SWING_CAP),
    )
    shift = abs(result.user.ros.score - result.user.ros.raw_score)
    assert shift <= DEFAULT_NEED_SWING_CAP + 1e-9


def test_long_term_grade_ignores_need_config_entirely():
    kwargs = dict(
        user_team_name="You",
        counterparty_team_name="Them",
        user_received=[_p("RB1", "RB", 100, 100)],
        user_given=[_p("WR1", "WR", 100, 120)],
        user_needs=SideNeeds(need_before=frozenset({"RB"}), need_after=frozenset({"WR"})),
        counterparty_needs=SideNeeds(),
    )
    a = evaluate_trade(**kwargs, cfg=TradeConfig())
    b = evaluate_trade(**kwargs, cfg=TradeConfig(need_boost=3.0, depth_discount=0.1, need_swing_cap=0.9))
    assert a.user.long_term.score == b.user.long_term.score
    assert a.user.long_term.grade == b.user.long_term.grade


# --- continuous league-relative need nudge (weakness maps) -------------------


def test_weakness_map_supersedes_the_binary_need_set():
    # No binary need, but the weakness map says RB is a below-average spot.
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("RB1", "RB", 100, 100)],
        user_given=[_p("WR1", "WR", 100, 100)],
        user_needs=SideNeeds(need_before=frozenset(), weakness_before={"RB": 1.10}),
        counterparty_needs=SideNeeds(),
    )
    assert result.user.ros.score > result.user.ros.raw_score


def test_weakness_after_map_dings_a_given_player():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("WR1", "WR", 100, 100)],
        user_given=[_p("RB1", "RB", 100, 100)],
        user_needs=SideNeeds(weakness_after={"RB": 1.10}),
        counterparty_needs=SideNeeds(),
    )
    assert result.user.ros.score < result.user.ros.raw_score


def test_empty_weakness_maps_fall_back_to_the_binary_need_model():
    kwargs = dict(
        user_team_name="You",
        counterparty_team_name="Them",
        user_received=[_p("RB1", "RB", 100, 100)],
        user_given=[_p("WR1", "WR", 100, 100)],
        counterparty_needs=SideNeeds(),
    )
    binary = evaluate_trade(**kwargs, user_needs=SideNeeds(need_before=frozenset({"RB"})))
    still_binary = evaluate_trade(
        **kwargs,
        user_needs=SideNeeds(need_before=frozenset({"RB"}), weakness_before={}, weakness_after={}),
    )
    assert still_binary.user.ros.score == binary.user.ros.score


def test_weakness_map_is_still_clamped_by_need_swing_cap():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("RB1", "RB", 100, 100)],
        user_given=[_p("WR1", "WR", 100, 100)],
        user_needs=SideNeeds(weakness_before={"RB": 5.0}),
        counterparty_needs=SideNeeds(),
    )
    shift = abs(result.user.ros.score - result.user.ros.raw_score)
    assert shift <= DEFAULT_NEED_SWING_CAP + 1e-9


def test_long_term_grade_ignores_weakness_maps():
    kwargs = dict(
        user_team_name="You",
        counterparty_team_name="Them",
        user_received=[_p("RB1", "RB", 100, 100)],
        user_given=[_p("WR1", "WR", 100, 120)],
        counterparty_needs=SideNeeds(),
    )
    plain = evaluate_trade(**kwargs, user_needs=SideNeeds())
    aggressive = evaluate_trade(
        **kwargs,
        user_needs=SideNeeds(weakness_before={"RB": 5.0}, weakness_after={"WR": 5.0}),
    )
    assert plain.user.long_term.score == aggressive.user.long_term.score
    assert plain.user.long_term.grade == aggressive.user.long_term.grade


def test_side_needs_defaults_keep_empty_weakness_maps():
    needs = SideNeeds()
    assert needs.weakness_before == {}
    assert needs.weakness_after == {}


def test_ros_uses_ros_value_and_long_term_uses_lt_value():
    # A is a win-now asset; B is a dynasty asset.
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("A", "RB", 150, 50)],
        user_given=[_p("B", "WR", 50, 150)],
        user_needs=SideNeeds(),
        counterparty_needs=SideNeeds(),
    )
    assert result.user.ros.score > 0  # you win the ROS side
    assert result.user.long_term.score < 0  # you lose the long-term side
    assert result.counterparty.long_term.score > 0


# --- callouts ---------------------------------------------------------------


def test_callout_flags_a_filled_need():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("RB1", "RB", 100, 100)],
        user_given=[_p("WR1", "WR", 100, 100)],
        user_needs=SideNeeds(need_before=frozenset({"RB"}), need_after=frozenset()),
        counterparty_needs=SideNeeds(),
    )
    assert any("fills" in c and "RB" in c for c in result.user.callouts)


def test_callout_flags_an_opened_hole():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("WR1", "WR", 100, 100)],
        user_given=[_p("TE1", "TE", 100, 100)],
        user_needs=SideNeeds(need_before=frozenset(), need_after=frozenset({"TE"})),
        counterparty_needs=SideNeeds(),
    )
    assert any("opens a hole at TE" in c for c in result.user.callouts)


def test_callout_warns_when_trade_pushes_you_over_the_roster_limit():
    over = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("a", "WR", 10, 10), _p("b", "WR", 10, 10)],
        user_given=[_p("c", "RB", 10, 10)],
        user_needs=SideNeeds(roster_size_before=15, roster_size_after=16, roster_capacity=15),
        counterparty_needs=SideNeeds(),
    )
    assert any("over the 15-man limit" in c for c in over.user.callouts)

    frees = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("c", "RB", 10, 10)],
        user_given=[_p("a", "WR", 10, 10), _p("b", "WR", 10, 10)],
        user_needs=SideNeeds(roster_size_before=15, roster_size_after=14, roster_capacity=15),
        counterparty_needs=SideNeeds(),
    )
    assert any("frees bench" in c for c in frees.user.callouts)


def test_callout_reports_signed_net_points_and_value():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("Get", "RB", 130, 140)],
        user_given=[_p("Give", "RB", 100, 100)],
        user_needs=SideNeeds(),
        counterparty_needs=SideNeeds(),
    )
    assert "net ROS points: +30.0" in result.user.callouts
    assert "net long-term value: +40.0" in result.user.callouts
    assert "net ROS points: -30.0" in result.counterparty.callouts


def test_evaluate_trade_returns_four_populated_grades():
    result = evaluate_trade(
        "You",
        "Them",
        user_received=[_p("A", "RB", 120, 130)],
        user_given=[_p("B", "WR", 90, 110)],
        user_needs=SideNeeds(),
        counterparty_needs=SideNeeds(),
    )
    for grade in (
        result.user.ros.grade,
        result.user.long_term.grade,
        result.counterparty.ros.grade,
        result.counterparty.long_term.grade,
    ):
        assert grade in {"A", "B+", "B", "B-", "C", "C-", "D", "D-", "F"}
