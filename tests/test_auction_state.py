import pytest

from empire_tools.auction.state import DraftState, Manager, Player


def make_state():
    managers = {
        "Alice": Manager(name="Alice", budget=200),
        "Bob": Manager(name="Bob", budget=200),
    }
    available = {
        "Justin Jefferson": Player(name="Justin Jefferson", position="WR", pro_team="MIN"),
        "Christian McCaffrey": Player(name="Christian McCaffrey", position="RB", pro_team="SF"),
    }
    return DraftState(managers=managers, available=available, roster_spots_per_manager=16)


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
