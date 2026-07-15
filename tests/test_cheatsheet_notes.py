from empire_tools.cheatsheet.notes import PlayerNotes, load_notes, load_notes_from_config


def test_missing_file_returns_empty_dict(tmp_path):
    assert load_notes(tmp_path / "does_not_exist.csv") == {}


def test_loads_tier_override_flags_and_notes(tmp_path):
    csv_path = tmp_path / "notes.csv"
    csv_path.write_text(
        "name,tier_override,flags,notes\n"
        "Breece Hall,1,camp-riser;depth-chart-battle,Locked into every-down role\n"
    )

    notes = load_notes(csv_path)

    assert notes["Breece Hall"] == PlayerNotes(
        tier_override=1,
        flags=["camp-riser", "depth-chart-battle"],
        notes="Locked into every-down role",
    )


def test_blank_optional_fields_default_sensibly(tmp_path):
    csv_path = tmp_path / "notes.csv"
    csv_path.write_text("name,tier_override,flags,notes\nSome Player,,,\n")

    notes = load_notes(csv_path)

    assert notes["Some Player"] == PlayerNotes(tier_override=None, flags=[], notes="")


def test_loads_window_fit_multiplier(tmp_path):
    csv_path = tmp_path / "notes.csv"
    csv_path.write_text("name,tier_override,flags,notes,window_fit\nAging Vet,,,,0.8\n")

    notes = load_notes(csv_path)

    assert notes["Aging Vet"].window_fit_multiplier == 0.8


def test_missing_window_fit_column_defaults_to_neutral(tmp_path):
    csv_path = tmp_path / "notes.csv"
    csv_path.write_text("name,tier_override,flags,notes\nSome Player,,,\n")

    notes = load_notes(csv_path)

    assert notes["Some Player"].window_fit_multiplier == 1.0


def test_load_notes_from_config_without_key_returns_empty_dict():
    assert load_notes_from_config({}) == {}


def test_load_notes_from_config_reads_cheatsheet_notes_csv_key(tmp_path):
    csv_path = tmp_path / "notes.csv"
    csv_path.write_text("name,tier_override,flags,notes\nSome Player,2,,\n")

    notes = load_notes_from_config({"cheatsheet": {"notes_csv": str(csv_path)}})

    assert notes["Some Player"].tier_override == 2
