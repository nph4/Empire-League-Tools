from dataclasses import dataclass

import pytest

from empire_tools.faab.suggest import (
    blend_percentiles,
    is_injury_reserve,
    live_weight_for_week,
    percentile_within_position,
    suggest_bid,
)


@dataclass
class FakePlayer:
    name: str
    position: str
    injuryStatus: str = "ACTIVE"


def make_free_agents():
    return [
        FakePlayer("Best WR", "WR"),
        FakePlayer("Mid WR", "WR"),
        FakePlayer("Worst WR", "WR"),
        FakePlayer("Only TE", "TE"),
    ]


def make_value_pool():
    return {"Best WR": 90.0, "Mid WR": 50.0, "Worst WR": 10.0, "Only TE": 20.0}


def test_percentile_best_at_position_is_one():
    players = make_free_agents()
    percentile = percentile_within_position(make_value_pool(), players, "Best WR")
    assert percentile == 1.0


def test_percentile_worst_at_position_is_zero():
    players = make_free_agents()
    percentile = percentile_within_position(make_value_pool(), players, "Worst WR")
    assert percentile == 0.0


def test_percentile_middle_ranked_is_between():
    players = make_free_agents()
    percentile = percentile_within_position(make_value_pool(), players, "Mid WR")
    assert percentile == 0.5


def test_percentile_lone_player_at_position_is_one():
    players = make_free_agents()
    percentile = percentile_within_position(make_value_pool(), players, "Only TE")
    assert percentile == 1.0


def test_percentile_ranking_is_scoped_to_own_position():
    # "Only TE" outvalues "Worst WR" but they're never compared - each
    # ranks only against free agents at their own position.
    players = make_free_agents()
    assert percentile_within_position(make_value_pool(), players, "Only TE") == 1.0
    assert percentile_within_position(make_value_pool(), players, "Worst WR") == 0.0


@pytest.mark.parametrize(
    "percentile,expected",
    [
        (1.0, 70),  # top available add: full max_share of remaining budget
        (0.0, 0),  # worst available add: nothing
        (0.5, round(200 * 0.35 * 0.25)),  # falls off with the square, not linearly
    ],
)
def test_suggest_bid_scales_with_percentile_squared(percentile, expected):
    bid = suggest_bid(remaining_budget=200, percentile=percentile, fills_need=True, max_share=0.35)
    assert bid == expected


def test_suggest_bid_respects_custom_max_share():
    bid = suggest_bid(remaining_budget=100, percentile=1.0, fills_need=True, max_share=0.5)
    assert bid == 50


def test_suggest_bid_discounts_bench_only_adds():
    needed = suggest_bid(remaining_budget=200, percentile=1.0, fills_need=True, max_share=0.35)
    bench_only = suggest_bid(
        remaining_budget=200, percentile=1.0, fills_need=False, max_share=0.35, bench_only_discount=0.4
    )
    assert bench_only == round(needed * 0.4)
    assert bench_only < needed


def test_is_injury_reserve_true_for_ir_status():
    assert is_injury_reserve(FakePlayer("Hurt Guy", "TE", injuryStatus="INJURY_RESERVE"))


@pytest.mark.parametrize("status", ["ACTIVE", "QUESTIONABLE", "OUT", "DOUBTFUL", None])
def test_is_injury_reserve_false_for_everything_else(status):
    assert not is_injury_reserve(FakePlayer("Fine Guy", "TE", injuryStatus=status))


def test_live_weight_starts_at_week_one_value():
    assert live_weight_for_week(1, start=0.4, end=0.9, ramp_weeks=8) == 0.4


def test_live_weight_reaches_end_value_at_ramp_week():
    assert live_weight_for_week(8, start=0.4, end=0.9, ramp_weeks=8) == pytest.approx(0.9)


def test_live_weight_holds_at_end_value_past_ramp_week():
    # Dynasty rank never drops to zero weight - it just stops gaining any
    # more once the live signal has fully ramped in.
    assert live_weight_for_week(17, start=0.4, end=0.9, ramp_weeks=8) == pytest.approx(0.9)


def test_live_weight_ramps_linearly_between_endpoints():
    midpoint = live_weight_for_week(4, start=0.0, end=1.0, ramp_weeks=7)
    assert midpoint == pytest.approx(0.5)


def test_blend_percentiles_weights_toward_live_signal():
    # Early season (low live_weight): dynasty rank still dominates.
    early = blend_percentiles(dynasty_percentile=1.0, live_percentile=0.0, live_weight=0.2)
    assert early == pytest.approx(0.8)

    # Mid-season (high live_weight): a stale dynasty rank can no longer
    # out-rank a free agent ESPN's live data says is producing nothing.
    late = blend_percentiles(dynasty_percentile=1.0, live_percentile=0.0, live_weight=0.9)
    assert late == pytest.approx(0.1)
