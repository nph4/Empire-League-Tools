import pytest

from empire_tools.auction.state import DraftState, Manager, Player
from empire_tools.auction.suggest import suggest_bid, suggest_targets


def make_state():
    managers = {
        "Alice": Manager(name="Alice", budget=200),
        "Bob": Manager(name="Bob", budget=200),
    }
    available = {
        "Justin Jefferson": Player(name="Justin Jefferson", position="WR", pro_team="MIN"),
        "Christian McCaffrey": Player(name="Christian McCaffrey", position="RB", pro_team="SF"),
        "Waiver Fodder": Player(name="Waiver Fodder", position="WR", pro_team="NYJ"),
    }
    value_pool = {
        "Justin Jefferson": 90.0,
        "Christian McCaffrey": 90.0,
        "Waiver Fodder": 20.0,
    }
    roster_spots = 2  # small on purpose so the reserved-dollar math is easy to check by hand
    return DraftState(managers=managers, available=available, roster_spots_per_manager=roster_spots), value_pool


def test_suggest_bid_splits_remaining_spendable_by_relative_value():
    state, value_pool = make_state()
    # remaining spendable = (200 + 200) - (2*2 roster spots) = 396
    # equal-value players split the pool 90/(90+90+20)=0.45 each
    bid = suggest_bid(state, value_pool, "Justin Jefferson")
    assert bid == round(1 + (90 / 200) * 396)


def test_overpaying_deflates_remaining_suggested_bids():
    state, value_pool = make_state()
    before = suggest_bid(state, value_pool, "Justin Jefferson")

    # Total league budget is fixed. Waiver Fodder sells for far more than
    # its baseline value implies, so that money is "wasted" relative to
    # value gained - less budget remains per unit of remaining value, so
    # remaining players get cheaper (deflation).
    state.record_sale("Waiver Fodder", "Bob", 100)

    after = suggest_bid(state, value_pool, "Justin Jefferson")
    assert after < before


def test_bargain_inflates_remaining_suggested_bids():
    state, value_pool = make_state()
    before = suggest_bid(state, value_pool, "Justin Jefferson")

    # Waiver Fodder sells for $1, well under its baseline value - the
    # "saved" budget relative to value spent means more money remains per
    # unit of remaining value, so remaining players get pricier (inflation).
    state.record_sale("Waiver Fodder", "Bob", 1)

    after = suggest_bid(state, value_pool, "Justin Jefferson")
    assert after > before


def test_suggest_bid_unknown_player_raises():
    state, value_pool = make_state()
    with pytest.raises(KeyError):
        suggest_bid(state, value_pool, "Nobody")


def test_suggest_targets_only_returns_affordable_players():
    state, value_pool = make_state()
    # Waiver Fodder's suggested bid is 41 (see splits test); leave Alice
    # just enough max_bid to afford it but not the pricier duo (179 each).
    state.managers["Alice"].spent = 158
    assert state.max_bid("Alice") == 41

    targets = suggest_targets(state, value_pool, "Alice")

    assert [name for name, _ in targets] == ["Waiver Fodder"]
    assert all(bid <= state.max_bid("Alice") for _, bid in targets)


def test_suggest_targets_sorted_best_value_first():
    state, value_pool = make_state()
    targets = suggest_targets(state, value_pool, "Bob")
    bids = [bid for _, bid in targets]
    assert bids == sorted(bids, reverse=True)
