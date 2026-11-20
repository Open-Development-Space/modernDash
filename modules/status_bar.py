from rich.padding import Padding
from rich.table import Table

from . import DashboardModule
from .context import Frame

MODULE = DashboardModule("status_bar", "Location and status", row=1, column=2)


def render(frame: Frame, note: str = ""):
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    left = f"{frame.location}  ·  {frame.now:%A, %B} {frame.now.day}"
    if note:
        left += f"  ·  {note}"
    right = "" if frame.weather else frame.status
    grid.add_row(left, right)
    return Padding(grid, (1, frame.padding))
