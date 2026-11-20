"""Location and date, plus a loading/offline message while weather is missing."""
from __future__ import annotations

from rich.padding import Padding
from rich.table import Table

from dashlib import Frame, Module
from dashlib.weather import service


class StatusBar(Module):
    name = "status_bar"
    title = "Status bar"
    description = "Location and date; shows weather loading status."
    sizes = {"slim": (1, 6), "wide": (1, 10), "full": (1, 14)}
    default_size = "wide"

    def render(self, frame: Frame):
        weather = service()
        weather.poll()
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", no_wrap=True, overflow="ellipsis")
        grid.add_column(justify="right", no_wrap=True)
        left = f"{weather.location_name}  ·  {frame.now:%A, %B} {frame.now.day}"
        right = "" if weather.latest else weather.status
        grid.add_row(left, right)
        return Padding(grid, (frame.vpad, frame.pad))
