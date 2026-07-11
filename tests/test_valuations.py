from dataclasses import dataclass

from empire_tools.valuations import build_value_pool, build_value_pool_from_config


@dataclass
class FakeProjectedPlayer:
    name: str
    projected_total_points: float


def test_csv_values_take_priority_over_fallback():
    csv_values = {"Justin Jefferson": 65.0}
    pool = build_value_pool(csv_values, [FakeProjectedPlayer("Justin Jefferson", 999)])
    assert pool["Justin Jefferson"] == 65.0


def test_fallback_players_never_exceed_the_csv_floor():
    csv_values = {"Justin Jefferson": 65.0, "Deep Sleeper": 1.0}
    fallback = [
        FakeProjectedPlayer("Undrafted Rookie", 300),
        FakeProjectedPlayer("Waiver Fodder", 10),
    ]
    pool = build_value_pool(csv_values, fallback)

    csv_floor = min(csv_values.values())
    assert pool["Undrafted Rookie"] <= csv_floor
    assert pool["Waiver Fodder"] <= csv_floor
    # highest-projected fallback player still ranks above lower-projected ones
    assert pool["Undrafted Rookie"] > pool["Waiver Fodder"]


def test_no_csv_uses_raw_projection_share():
    pool = build_value_pool({}, [FakeProjectedPlayer("Only Option", 200)])
    assert pool["Only Option"] == 1.0


def test_build_value_pool_from_config_reads_values_csv_key(tmp_path):
    csv_path = tmp_path / "values.csv"
    csv_path.write_text("name,value\nJustin Jefferson,65\n")

    pool = build_value_pool_from_config(
        {"values_csv": str(csv_path)}, [FakeProjectedPlayer("Waiver Fodder", 50)]
    )

    assert pool["Justin Jefferson"] == 65.0
    assert pool["Waiver Fodder"] <= 65.0


def test_build_value_pool_from_config_without_csv_key_uses_fallback_only():
    pool = build_value_pool_from_config({}, [FakeProjectedPlayer("Only Option", 200)])
    assert pool["Only Option"] == 1.0
