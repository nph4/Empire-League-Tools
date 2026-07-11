from dataclasses import dataclass

import pytest

from empire_tools.faab.suggest import percentile_within_position, suggest_bid


@dataclass
class FakePlayer:
    name: str
    position: str


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
