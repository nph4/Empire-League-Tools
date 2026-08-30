from dataclasses import dataclass

import pytest

from empire_tools.valuations import (
    build_value_pool,
    build_value_pool_from_config,
    load_csv_values,
)

# Header line from a real FantasyPros dynasty rankings export.
FP_HEADER = '"RK",TIERS,"PLAYER NAME",TEAM,"POS","AGE","BEST","WORST","AVG.","STD.DEV","ECR VS. ADP"'


def load_csv_values_from_text(text, tmp_path=None, **kwargs):
    """Write `text` to a temp CSV and load it through load_csv_values."""
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(
        "w", suffix=".csv", delete=False, newline=""
    ) as f:
        f.write(text)
        path = Path(f.name)
    try:
        return load_csv_values(path, **kwargs)
    finally:
        path.unlink(missing_ok=True)


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


def test_name_value_csv_still_loads_and_ignores_blank_rows():
    values = load_csv_values_from_text("name,value\nJa'Marr Chase,9999\n,\nPuka Nacua,8800\n")
    assert values == {"Ja'Marr Chase": 9999.0, "Puka Nacua": 8800.0}


def test_fantasypros_rankings_export_converts_rank_to_a_descending_value_curve():
    text = "\n".join(
        [
            FP_HEADER,
            '"1",1,"Ja\'Marr Chase",CIN,"WR1","26","1","3","1.3","0.6","-"',
            '"2",1,"Bijan Robinson",ATL,"RB1","24","2","5","3.5","1.2","-"',
            '"30",4,"Some Guy",FA,"WR12","27","20","45","31.0","6.0","-"',
        ]
    )
    values = load_csv_values_from_text(text)

    assert set(values) == {"Ja'Marr Chase", "Bijan Robinson", "Some Guy"}
    # order follows rank
    assert values["Ja'Marr Chase"] > values["Bijan Robinson"] > values["Some Guy"]
    # exponential, not linear: the #1 -> #30 drop is far bigger than #1 -> #2
    assert (values["Ja'Marr Chase"] - values["Bijan Robinson"]) < (
        values["Bijan Robinson"] - values["Some Guy"]
    )


def test_fantasypros_rankings_export_prefers_avg_rank_over_integer_rk():
    # RK ties are broken by AVG.: same RK, different AVG. -> different values.
    text = "\n".join(
        [
            FP_HEADER,
            '"5",1,"Higher Avg",BUF,"RB3","25","3","9","5.1","1.0","-"',
            '"5",1,"Lower Avg",DAL,"WR4","24","4","8","5.9","1.0","-"',
        ]
    )
    values = load_csv_values_from_text(text)
    assert values["Higher Avg"] > values["Lower Avg"]


def test_smaller_half_life_makes_the_curve_steeper():
    text = "\n".join(
        [
            FP_HEADER,
            '"1",1,"Rank One",CIN,"WR1","26","1","3","1.0","0.5","-"',
            '"20",3,"Rank Twenty",ATL,"RB6","24","15","30","20.0","4.0","-"',
        ]
    )
    steep = load_csv_values_from_text(text, rank_curve_half_life=5)
    shallow = load_csv_values_from_text(text, rank_curve_half_life=60)

    steep_ratio = steep["Rank Twenty"] / steep["Rank One"]
    shallow_ratio = shallow["Rank Twenty"] / shallow["Rank One"]
    assert steep_ratio < shallow_ratio


def test_non_positive_half_life_falls_back_to_default():
    text = "\n".join(
        [
            FP_HEADER,
            '"1",1,"Rank One",CIN,"WR1","26","1","3","1.0","0.5","-"',
            '"20",3,"Rank Twenty",ATL,"RB6","24","15","30","20.0","4.0","-"',
        ]
    )
    default = load_csv_values_from_text(text)
    zeroed = load_csv_values_from_text(text, rank_curve_half_life=0)
    assert zeroed == default


def test_unrecognized_csv_header_raises(tmp_path):
    path = tmp_path / "mystery.csv"
    path.write_text("player,rating\nJa'Marr Chase,10\n")
    with pytest.raises(ValueError, match="unrecognized value CSV"):
        load_csv_values(path)


def test_build_value_pool_from_config_loads_a_fantasypros_export(tmp_path):
    path = tmp_path / "fp_dynasty.csv"
    path.write_text(
        "\n".join(
            [
                FP_HEADER,
                '"1",1,"Ja\'Marr Chase",CIN,"WR1","26","1","3","1.3","0.6","-"',
                '"2",1,"Bijan Robinson",ATL,"RB1","24","2","5","3.5","1.2","-"',
            ]
        )
    )
    pool = build_value_pool_from_config(
        {"values_csv": str(path)},
        [FakeProjectedPlayer("Top Waiver Guy", 200), FakeProjectedPlayer("Deep Waiver Guy", 50)],
    )

    assert pool["Ja'Marr Chase"] > pool["Bijan Robinson"]
    # ranked players are never outranked by an unranked ESPN fallback
    assert pool["Bijan Robinson"] >= pool["Top Waiver Guy"] > pool["Deep Waiver Guy"]
