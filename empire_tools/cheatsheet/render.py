"""Pure formatting of cheat sheet rows - no I/O. `cli.py` decides whether
the result goes to stdout or a file."""

import csv
import io

from empire_tools.cheatsheet.build import CheatSheetRow


def render_markdown(rows: list[CheatSheetRow]) -> str:
    """One table per position, best tier first - meant to be printed or
    viewed as a formatted page rather than filtered/sorted."""
    sections = []
    current_position = None
    table_rows: list[str] = []

    def flush():
        if current_position is not None:
            header = "| Tier | Player | Team | Value | Flags | Notes |\n|---|---|---|---|---|---|"
            sections.append(f"## {current_position}\n\n{header}\n" + "\n".join(table_rows))

    for row in rows:
        if row.position != current_position:
            flush()
            current_position = row.position
            table_rows = []
        flags = "; ".join(row.flags)
        table_rows.append(f"| {row.tier} | {row.name} | {row.pro_team} | {row.value:.1f} | {flags} | {row.notes} |")
    flush()

    return "\n\n".join(sections)


def render_csv(rows: list[CheatSheetRow]) -> str:
    """Flat rows, sortable/filterable in a spreadsheet."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["position", "tier", "name", "pro_team", "value", "flags", "notes"])
    for row in rows:
        writer.writerow([row.position, row.tier, row.name, row.pro_team, f"{row.value:.1f}", ";".join(row.flags), row.notes])
    return buffer.getvalue().rstrip("\n")
