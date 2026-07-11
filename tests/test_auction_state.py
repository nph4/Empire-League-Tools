import pytest

from empire_tools.auction.state import DraftState, Manager, Player
from empire_tools.roster import RosterRequirements


def make_state():
    requirements = RosterRequirements(starters={}, flex_spots=0, bench_spots=16)
    managers = {
        "Alice": Manager.new("Alice", 200, requirements),
        "Bob": Manager.new("Bob", 200, requirements),
    }
    available = {
        "Justin Jefferson": Player(name="Justin Jefferson", position="WR", pro_team="MIN"),
        "Christian McCaffrey": Player(name="Christian McCaffrey", position="RB", pro_team="SF"),
    }
    return DraftState(managers=managers, available=available, requirements=requirements)


def test_record_sale_updates_manager_and_pool():
    state = make_state()
    sale = state.record_sale("Justin Jefferson", "Alice", 55)

    assert sale.amount == 55
    assert state.managers["Alice"].spent == 55
    assert state.managers["Alice"].roster_size == 1
    assert "Justin Jefferson" not in state.available


def test_record_sale_rejects_overspend():
    state = make_state()
    with pytest.raises(ValueError):
        state.record_sale("Justin Jefferson", "Alice", 500)


def test_record_sale_rejects_unknown_player():
    state = make_state()
    with pytest.raises(KeyError):
        state.record_sale("Nobody", "Alice", 10)


def test_max_bid_reserves_a_dollar_per_remaining_roster_spot():
    state = make_state()
    state.managers["Alice"].roster_size = 15  # one spot left before this pick
    assert state.max_bid("Alice") == state.managers["Alice"].remaining
