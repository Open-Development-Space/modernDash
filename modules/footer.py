from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from . import DashboardModule
from .context import Frame

MODULE = DashboardModule("footer", "Update footer", row=1, column=12)


def render(frame: Frame):
    if not frame.weather:
        return Text("")
    updated = (
        f"Updated {frame.weather.fetched_at:%I:%M %p}  ·  {frame.version}"
    ).replace("Updated 0", "Updated ")
    if frame.stale:
        updated += " (offline)"
    grid = Table.grid(expand=True)
    grid.add_column(justify="right")
    grid.add_row(Text(updated, style="dim"))
    return Padding(grid, (0, 1, 0, frame.padding))
