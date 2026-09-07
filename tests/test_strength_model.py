import statistics

import pytest

from empire_tools.roster import RosterRequirements
from empire_tools.strength.model import (
    DEFAULT_BENCH_DEPTH_WEIGHT,
    STRONG_Z,
    WEAK_Z,
    classify_strength,
    corps_strength_by_position,
    league_positional_strength,
    team_weakness_multipliers,
    weakness_multiplier,
)


def make_requirements():
    return RosterRequirements(
        starters={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "D/ST": 1, "K": 1},
        flex_spots=1,
        flex_eligible=frozenset({"RB", "WR", "TE"}),
        bench_spots=6,
    )


# --- corps_strength_by_position ---------------------------------------------


def test_starters_count_at_full_weight():
    strength = corps_strength_by_position([("RB", 100.0), ("RB", 80.0)], make_requirements())
    assert strength["RB"] == pytest.approx(180.0)


def test_bench_depth_is_discounted():
    # 2 RB starters + 1 flex take the top 3; the 4th RB is bench depth.
    strength = corps_strength_by_position(
        [("RB", 100.0), ("RB", 80.0), ("RB", 60.0), ("RB", 40.0)], make_requirements()
    )
    assert strength["RB"] == pytest.approx(100 + 80 + 60 + DEFAULT_BENCH_DEPTH_WEIGHT * 40)


def test_flex_slot_credits_the_occupant_position_at_full_weight():
    # 3 RBs, 2 WRs, 1 TE: the 3rd RB mans the flex and counts at full weight.
    strength = corps_strength_by_position(
        [("RB", 100.0), ("RB", 90.0), ("RB", 80.0), ("WR", 50.0), ("WR", 50.0), ("TE", 30.0)],
        make_requirements(),
    )
    assert strength["RB"] == pytest.approx(270.0)  # 100 + 90 + 80, not 190 + 0.4*80


def test_flex_goes_to_the_best_remaining_flex_eligible_by_value():
    # RB surplus is worth 20, WR surplus 60 -> WR takes the flex, RB drops to bench.
    strength = corps_strength_by_position(
        [("RB", 100.0), ("RB", 90.0), ("RB", 20.0), ("WR", 80.0), ("WR", 70.0), ("WR", 60.0)],
        make_requirements(),
    )
    assert strength["WR"] == pytest.approx(150 + 60)
    assert strength["RB"] == pytest.approx(190 + DEFAULT_BENCH_DEPTH_WEIGHT * 20)


def test_position_with_no_players_is_zero():
    strength = corps_strength_by_position([("QB", 100.0)], make_requirements())
    assert strength["RB"] == 0.0
    assert strength["QB"] == pytest.approx(100.0)


def test_fewer_players_than_starter_slots_just_sums_them():
    strength = corps_strength_by_position([("RB", 100.0)], make_requirements())
    assert strength["RB"] == pytest.approx(100.0)


def test_dst_has_no_flex_and_a_bench_norm():
    # D/ST isn't flex-eligible, so the 2nd one is straight bench depth.
    strength = corps_strength_by_position([("D/ST", 50.0), ("D/ST", 40.0)], make_requirements())
    assert strength["D/ST"] == pytest.approx(50 + DEFAULT_BENCH_DEPTH_WEIGHT * 40)


# --- league_positional_strength -------------------------------------------


def _rb_only_league(strengths_by_team):
    reqs = make_requirements()
    rosters = {name: [("RB", value)] for name, value in strengths_by_team.items()}
    return league_positional_strength(rosters, reqs), reqs


def test_mean_and_pstdev_match_manual():
    league, _ = _rb_only_league({"A": 100.0, "B": 200.0, "C": 300.0})
    rb = league.positions["RB"]
    assert rb.mean == pytest.approx(200.0)
    assert rb.stdev == pytest.approx(statistics.pstdev([100.0, 200.0, 300.0]))
    assert rb.standings["A"].z == pytest.approx((100.0 - 200.0) / rb.stdev)


def test_z_is_zero_when_all_teams_equal():
    league, _ = _rb_only_league({"A": 100.0, "B": 100.0, "C": 100.0})
    assert all(s.z == 0.0 for s in league.positions["RB"].standings.values())


def test_rank_one_is_strongest():
    league, _ = _rb_only_league({"A": 100.0, "B": 200.0, "C": 300.0})
    standings = league.positions["RB"].standings
    assert standings["C"].rank == 1
    assert standings["A"].rank == 3


def test_ranks_tie_and_skip():
    league, _ = _rb_only_league({"A": 200.0, "B": 200.0, "C": 100.0})
    standings = league.positions["RB"].standings
    assert standings["A"].rank == 1
    assert standings["B"].rank == 1
    assert standings["C"].rank == 3


def test_single_team_league_does_not_crash():
    league, _ = _rb_only_league({"A": 100.0})
    rb = league.positions["RB"].standings["A"]
    assert rb.z == 0.0
    assert rb.rank == 1
    assert rb.team_count == 1


def test_is_degenerate_true_when_all_values_zero():
    league = league_positional_strength({"A": [], "B": []}, make_requirements())
    assert league.is_degenerate


def test_is_degenerate_false_when_any_value_nonzero():
    league, _ = _rb_only_league({"A": 0.0, "B": 1.0})
    assert not league.is_degenerate


def test_weak_spots_sorted_ascending_by_z_and_limit_respected():
    reqs = make_requirements()
    rosters = {
        "Me": [("RB", 300.0), ("WR", 10.0), ("TE", 10.0)],
        "Rival": [("RB", 10.0), ("WR", 300.0), ("TE", 300.0)],
    }
    league = league_positional_strength(rosters, reqs)
    weak = league.weak_spots("Me")
    assert weak[0][0] in {"WR", "TE"}  # both are Me's weak spots
    assert weak[-1][0] == "RB"  # RB is Me's strength
    assert league.weak_spots("Me", limit=1) == weak[:1]


# --- weakness_multiplier --------------------------------------------------

_BOUNDS = dict(need_boost=1.10, depth_discount=0.90)


def test_center_is_one():
    assert weakness_multiplier(0.0, **_BOUNDS) == pytest.approx(1.0)


def test_weak_side_reaches_need_boost_at_negative_z_span():
    assert weakness_multiplier(-1.5, z_span=1.5, **_BOUNDS) == pytest.approx(1.10)


def test_strong_side_reaches_depth_discount_at_positive_z_span():
    assert weakness_multiplier(1.5, z_span=1.5, **_BOUNDS) == pytest.approx(0.90)


def test_saturates_beyond_span():
    assert weakness_multiplier(-10.0, z_span=1.5, **_BOUNDS) == pytest.approx(1.10)
    assert weakness_multiplier(10.0, z_span=1.5, **_BOUNDS) == pytest.approx(0.90)


@pytest.mark.parametrize("z", [-6, -4, -2, -1, 0, 1, 2, 4, 6])
def test_bounded_across_wide_z_range(z):
    m = weakness_multiplier(float(z), z_span=1.5, **_BOUNDS)
    assert 0.90 - 1e-9 <= m <= 1.10 + 1e-9


def test_handles_asymmetric_bounds():
    bounds = dict(need_boost=1.30, depth_discount=0.95)
    assert weakness_multiplier(0.0, z_span=1.5, **bounds) == pytest.approx(1.0)
    assert weakness_multiplier(-1.5, z_span=1.5, **bounds) == pytest.approx(1.30)
    assert weakness_multiplier(1.5, z_span=1.5, **bounds) == pytest.approx(0.95)


def test_team_weakness_multipliers_covers_every_scored_position():
    league, _ = _rb_only_league({"A": 100.0, "B": 300.0})
    maps = team_weakness_multipliers(league, "A", z_span=1.5, **_BOUNDS)
    assert set(maps) == set(league.positions)
    assert maps["RB"] > 1.0  # A is the weaker RB team


# --- classify_strength --------------------------------------------------


@pytest.mark.parametrize(
    "z,verdict",
    [
        (WEAK_Z, "weak spot"),
        (WEAK_Z + 0.01, "average"),
        (0.0, "average"),
        (STRONG_Z - 0.01, "average"),
        (STRONG_Z, "strength"),
    ],
)
def test_classify_strength_thresholds(z, verdict):
    assert classify_strength(z) == verdict
