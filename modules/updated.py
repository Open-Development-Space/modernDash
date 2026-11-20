"""Dim "Updated 4:42 PM · version" line, right-aligned."""
from __future__ import annotations

from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from dashlib import Frame, Module
from dashlib.weather import service


class Updated(Module):
    name = "updated"
    title = "Update footer"
    description = "When weather was last refreshed, and the dashboard version."
    sizes = {"slim": (1, 6), "full": (1, 14)}
    default_size = "full"

    def render(self, frame: Frame):
        weather = service()
        weather.poll()
        data = weather.latest
        if not data:
            return Text("")
        updated = f"Updated {data.fetched_at:%I:%M %p}  ·  {frame.config.get('version', '')}".replace("Updated 0", "Updated ")
        if weather.failing:
            updated += " (offline)"
        grid = Table.grid(expand=True)
        grid.add_column(justify="right")
        grid.add_row(Text(updated, style="dim"))
        return Padding(grid, (0, 1, 0, frame.pad))
