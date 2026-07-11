from empire_tools.auction.state import DraftState, Manager, Player
from empire_tools.roster import RosterRequirements


def make_state():
    requirements = RosterRequirements(
        starters={"QB": 1, "RB": 2, "WR": 2, "TE": 1},
        flex_spots=1,
        flex_eligible=frozenset({"RB", "WR", "TE"}),
        bench_spots=2,
    )
    managers = {"Alice": Manager.new("Alice", 200, requirements)}
    available = {
        name: Player(name=name, position=position, pro_team="XXX")
        for name, position in [
            ("QB1", "QB"),
            ("RB1", "RB"),
            ("RB2", "RB"),
            ("RB3", "RB"),
            ("WR1", "WR"),
        ]
    }
    return DraftState(managers=managers, available=available, requirements=requirements)


def test_needed_positions_includes_open_starters_and_flex_eligible():
    state = make_state()
    needed = state.needed_positions("Alice")
    # QB/RB/WR/TE starters all open, plus RB/WR/TE via the open flex spot
    assert needed == {"QB", "RB", "WR", "TE"}


def test_needed_positions_excludes_filled_starters_still_flex_eligible():
    state = make_state()
    state.record_sale("QB1", "Alice", 10)
    # QB starter is now filled and QB isn't flex-eligible here, so QB drops out
    assert "QB" not in state.needed_positions("Alice")


def test_fill_slot_prefers_exact_starter_over_flex_over_bench():
    state = make_state()

    state.record_sale("RB1", "Alice", 10)  # fills the RB starter slot
    manager = state.managers["Alice"]
    assert manager.starters_remaining["RB"] == 1
    assert manager.flex_remaining == 1
    assert manager.bench_remaining == 2

    state.record_sale("RB2", "Alice", 10)  # fills the last RB starter slot
    assert manager.starters_remaining["RB"] == 0
    assert manager.flex_remaining == 1

    state.record_sale("RB3", "Alice", 10)  # no RB starter slot left, spills into flex
    assert manager.flex_remaining == 0
    assert manager.bench_remaining == 2

    state.record_sale("WR1", "Alice", 10)  # WR starter still open, doesn't touch bench
    assert manager.starters_remaining["WR"] == 1
    assert manager.bench_remaining == 2
