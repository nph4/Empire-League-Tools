"""The hand-maintained overlay on top of computed value/tiers: tier
overrides, situational flags (e.g. camp-riser, depth-chart-battle), and
free-text notes. This is the part of the cheat sheet meant to be edited
repeatedly between now and draft day as camp/preseason news comes in - it's
never overwritten by regenerating the sheet, only read.

Optional, same as valuations.py's values_csv: a missing file just means no
manual annotations yet, not an error.
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PlayerNotes:
    tier_override: int | None = None
    flags: list[str] = field(default_factory=list)
    notes: str = ""


def load_notes(path: Path) -> dict[str, PlayerNotes]:
    """Load a CSV of `name,tier_override,flags,notes` rows into a
    {name: PlayerNotes} dict. `flags` is a semicolon-separated list of
    freeform tags. Returns an empty dict if the file doesn't exist yet."""
    path = Path(path)
    if not path.exists():
        return {}

    result: dict[str, PlayerNotes] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            tier_override_raw = (row.get("tier_override") or "").strip()
            flags_raw = (row.get("flags") or "").strip()
            result[row["name"]] = PlayerNotes(
                tier_override=int(tier_override_raw) if tier_override_raw else None,
                flags=[flag.strip() for flag in flags_raw.split(";") if flag.strip()],
                notes=(row.get("notes") or "").strip(),
            )
    return result


def load_notes_from_config(config: dict) -> dict[str, PlayerNotes]:
    """Convenience wrapper: load config's optional `cheatsheet.notes_csv`."""
    csv_path = config.get("cheatsheet", {}).get("notes_csv")
    return load_notes(csv_path) if csv_path else {}
