"""Baseline player values feeding the bid-suggestion model.

Values come from a user-supplied CSV (dynasty rankings/values exported from
somewhere like KeepTradeCut or FantasyPros — whatever scale you like, only
relative order/magnitude within the file matters). Any player ESPN knows
about but that's missing from the CSV falls back to a value derived from
ESPN's projected_total_points, scaled down so a fallback player can never
outrank someone you explicitly ranked — the CSV is assumed to cover every
dynasty-relevant asset, so a name missing from it is presumed to be replacement
level or worse.
"""

import csv
from pathlib import Path
from typing import Protocol


class ProjectsPoints(Protocol):
    name: str
    projected_total_points: float


def load_csv_values(path: Path) -> dict[str, float]:
    """Load a CSV of `name,value` rows into a {name: value} dict."""
    values: dict[str, float] = {}
    with Path(path).open(newline="") as f:
        for row in csv.DictReader(f):
            values[row["name"]] = float(row["value"])
    return values


def build_value_pool(
    csv_values: dict[str, float], fallback_players: list[ProjectsPoints]
) -> dict[str, float]:
    """Merge CSV values with an ESPN-projection-based fallback for any
    player in `fallback_players` that isn't already in `csv_values`."""
    pool = dict(csv_values)

    missing = [p for p in fallback_players if p.name not in pool]
    if not missing:
        return pool

    max_proj = max((p.projected_total_points for p in missing), default=0) or 1
    ceiling = min(csv_values.values()) if csv_values else None

    for player in missing:
        share = player.projected_total_points / max_proj
        pool[player.name] = share * ceiling if ceiling is not None else share

    return pool
