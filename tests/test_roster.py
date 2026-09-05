from empire_tools.roster import RosterRequirements, needed_positions, requirements_from_espn_slot_counts


def test_requirements_from_espn_slot_counts_separates_flex_bench_and_dst():
    parsed = requirements_from_espn_slot_counts(
        {
            "QB": 1,
            "RB": 2,
            "RB/WR": 0,
            "WR": 2,
            "WR/TE": 0,
            "TE": 1,
            "RB/WR/TE": 1,
            "D/ST": 1,
            "K": 1,
            "BE": 7,
            "IR": 1,
        }
    )

    assert parsed.starters == {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "D/ST": 1, "K": 1}
    assert parsed.flex_spots == 1
    assert parsed.flex_eligible == {"RB", "WR", "TE"}
    assert parsed.bench_spots == 7  # BE only
    assert parsed.ir_spots == 1  # IR tracked separately, not drafted into
    # IR excluded: total is starters + flex + bench, not IR
    assert parsed.total_spots == 1 + 2 + 2 + 1 + 1 + 1 + 1 + 7


def make_requirements():
    return RosterRequirements(
        starters={"QB": 1, "RB": 2, "WR": 2, "TE": 1},
        flex_spots=1,
        flex_eligible=frozenset({"RB", "WR", "TE"}),
        bench_spots=2,
    )


def test_needed_positions_empty_roster_needs_every_starter_and_flex():
    requirements = make_requirements()
    assert needed_positions(requirements, []) == {"QB", "RB", "WR", "TE"}


def test_needed_positions_drops_filled_single_position_starters():
    requirements = make_requirements()
    needed = needed_positions(requirements, ["QB"])
    assert "QB" not in needed
    assert needed == {"RB", "WR", "TE"}


def test_needed_positions_extra_rb_fills_flex_not_a_second_rb_starter():
    requirements = make_requirements()
    # 2 RBs fill both RB starter slots; a 3rd RB spills into the flex spot,
    # closing out RB/WR/TE flex eligibility entirely.
    needed = needed_positions(requirements, ["RB", "RB", "RB"])
    assert needed == {"QB", "WR", "TE"}


def test_needed_positions_roster_full_at_starters_and_flex_is_empty():
    requirements = make_requirements()
    needed = needed_positions(requirements, ["QB", "RB", "RB", "WR", "WR", "TE", "WR"])
    assert needed == set()


def test_needed_positions_bench_overflow_does_not_affect_needs():
    requirements = make_requirements()
    # Way more players than roster spots exist - extras just don't fit
    # anywhere trackable here, shouldn't raise or change what's needed.
    needed = needed_positions(requirements, ["QB"] * 5)
    assert needed == {"RB", "WR", "TE"}
