from empire_tools.cheatsheet.build import CheatSheetRow
from empire_tools.cheatsheet.render import render_csv, render_markdown


def test_render_markdown_groups_rows_into_one_section_per_position():
    rows = [
        CheatSheetRow("QB One", "QB", "BUF", 90.0, 1, [], ""),
        CheatSheetRow("RB One", "RB", "KC", 80.0, 1, ["camp-riser"], "Bell cow"),
    ]
    output = render_markdown(rows)

    assert "## QB" in output
    assert "## RB" in output
    assert "QB One" in output
    assert output.index("## QB") < output.index("## RB")
    assert "camp-riser" in output and "Bell cow" in output


def test_render_markdown_empty_rows_returns_empty_string():
    assert render_markdown([]) == ""


def test_render_csv_has_header_and_one_line_per_row():
    rows = [CheatSheetRow("RB One", "RB", "KC", 80.0, 1, ["camp-riser", "depth-chart-battle"], "Bell cow")]
    output = render_csv(rows)
    lines = output.splitlines()

    assert lines[0] == "position,tier,name,pro_team,value,flags,notes"
    assert lines[1] == "RB,1,RB One,KC,80.0,camp-riser;depth-chart-battle,Bell cow"


def test_render_csv_quotes_fields_containing_commas():
    rows = [CheatSheetRow("Player, Jr.", "WR", "DAL", 10.0, 1, [], "solid, not great")]
    output = render_csv(rows)
    assert '"Player, Jr."' in output
    assert '"solid, not great"' in output
