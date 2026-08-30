"""Baseline player values feeding the bid-suggestion model.

Values come from a user-supplied CSV (dynasty rankings/values exported from
somewhere like KeepTradeCut or FantasyPros — whatever scale you like, only
relative order/magnitude within the file matters). Any player ESPN knows
about but that's missing from the CSV falls back to a value derived from
ESPN's projected_total_points, scaled down so a fallback player can never
outrank someone you explicitly ranked — the CSV is assumed to cover every
dynasty-relevant asset, so a name missing from it is presumed to be replacement
level or worse.

Two CSV shapes are accepted, auto-detected from the header (see
`load_csv_values`): a `name,value` file (a KeepTradeCut-style *value* export,
or anything you hand-maintain), or a raw FantasyPros *rankings* export
(`RK,TIERS,PLAYER NAME,...`), which has ranks but no values — the rank is
converted to a value curve so the export drops in without hand-editing.
"""

import csv
from pathlib import Path
from typing import Iterable, Protocol

# How many ranks it takes a FantasyPros-rankings value to halve. A consensus
# #1 should be worth dramatically more than a #30 (auction dollars concentrate
# at the top), so rank is mapped through an exponential decay rather than a
# straight line. Overridable via `values_csv_rank_half_life` in config.yaml.
DEFAULT_RANK_CURVE_HALF_LIFE = 30.0

# Arbitrary top-of-curve value for the rank -> value mapping. Only ratios
# between values matter downstream, so the absolute scale is cosmetic.
_RANK_CURVE_TOP = 1000.0


class ProjectsPoints(Protocol):
    name: str
    projected_total_points: float


def _normalize_header(name: str) -> str:
    return name.strip().strip('"').strip().upper()


def _first_present(headers: dict[str, str], *candidates: str) -> str | None:
    """Return the original header name for the first candidate (given
    normalized) that's present, or None."""
    for candidate in candidates:
        if candidate in headers:
            return headers[candidate]
    return None


def _rank_to_value(rank: float, half_life: float) -> float:
    return _RANK_CURVE_TOP * 0.5 ** ((rank - 1.0) / half_life)


def _rankings_to_values(
    rows: Iterable[dict], headers: dict[str, str], half_life: float
) -> dict[str, float]:
    """Convert a FantasyPros rankings export's rows into {name: value},
    preferring the fractional average expert rank (`AVG.`) over the integer
    overall rank (`RK`) when it's available."""
    name_col = headers["PLAYER NAME"]
    rank_col = _first_present(headers, "AVG.", "AVG", "RK")
    if rank_col is None:
        raise ValueError(
            "FantasyPros rankings export has a 'PLAYER NAME' column but no "
            "'AVG.' or 'RK' rank column to derive a value from."
        )

    values: dict[str, float] = {}
    for row in rows:
        name = (row.get(name_col) or "").strip()
        if not name:
            continue
        raw_rank = (row.get(rank_col) or "").strip()
        try:
            rank = float(raw_rank)
        except ValueError:
            continue
        values[name] = _rank_to_value(rank, half_life)
    return values


def load_csv_values(
    path: Path, rank_curve_half_life: float = DEFAULT_RANK_CURVE_HALF_LIFE
) -> dict[str, float]:
    """Load a player-value CSV into a {name: value} dict.

    Accepts either format, auto-detected from the header:

    * ``name,value`` — taken as-is (any scale; only relative order/magnitude
      matters).
    * A raw FantasyPros *rankings* export (``RK,TIERS,PLAYER NAME,TEAM,POS,
      ...``) — has ranks but no values, so the overall rank (``AVG.`` average
      expert rank when present, else ``RK``) is mapped to a value with an
      exponential decay (``_rank_to_value``); ``rank_curve_half_life`` is how
      many ranks it takes for value to halve.
    """
    half_life = rank_curve_half_life if rank_curve_half_life and rank_curve_half_life > 0 else DEFAULT_RANK_CURVE_HALF_LIFE

    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = {_normalize_header(h): h for h in (reader.fieldnames or [])}

        if "NAME" in headers and "VALUE" in headers:
            name_col, value_col = headers["NAME"], headers["VALUE"]
            values: dict[str, float] = {}
            for row in reader:
                name = (row.get(name_col) or "").strip()
                if name:
                    values[name] = float(row[value_col])
            return values

        if "PLAYER NAME" in headers:
            return _rankings_to_values(reader, headers, half_life)

    raise ValueError(
        f"{path}: unrecognized value CSV. Expected either a 'name,value' header "
        f"or a FantasyPros rankings export with a 'PLAYER NAME' column; got "
        f"columns {sorted(headers)}."
    )


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


def build_value_pool_from_config(config: dict, free_agents: list[ProjectsPoints]) -> dict[str, float]:
    """Convenience wrapper: load config's optional `values_csv` (shared by
    the auction and FAAB tools) and merge it with an ESPN fallback."""
    csv_path = config.get("values_csv")
    half_life = config.get("values_csv_rank_half_life") or DEFAULT_RANK_CURVE_HALF_LIFE
    csv_values = load_csv_values(csv_path, half_life) if csv_path else {}
    return build_value_pool(csv_values, free_agents)
