"""A clock, with the date underneath when the module is two rows tall."""
from __future__ import annotations

from rich.console import Group
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from dashlib import Frame, Module


class Clock(Module):
    name = "clock"
    title = "Clock"
    description = "Current time (options: seconds, hour24)."
    sizes = {"small": (1, 2), "medium": (1, 4), "tall": (2, 4)}
    default_size = "medium"
    defaults = {"seconds": True, "hour24": False}

    def render(self, frame: Frame):
        seconds, hour24 = self.option("seconds"), self.option("hour24")
        fmt = ("%H:%M" if hour24 else "%I:%M") + (":%S" if seconds else "") + ("" if hour24 else " %p")
        clock = frame.now.strftime(fmt)
        if not hour24:
            clock = clock.lstrip("0")
        parts = [Text(clock, style="bold", no_wrap=True, justify="right")]
        if frame.height >= 2 and frame.rows >= 2:
            parts.append(Text(frame.now.strftime("%a %b ") + str(frame.now.day), style="dim", justify="right", no_wrap=True))
        grid = Table.grid(expand=True)
        grid.add_column(justify="right")
        grid.add_row(Group(*parts))
        return Padding(grid, (frame.vpad if len(parts) == 1 else 0, frame.pad))
