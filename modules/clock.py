from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from . import DashboardModule
from .context import Frame

MODULE = DashboardModule("clock", "Clock", row=1, column=1)


def render(frame: Frame):
    grid = Table.grid(expand=True)
    grid.add_column(justify="right")
    grid.add_row(Text(frame.now.strftime("%I:%M:%S %p").lstrip("0"), style="bold"))
    return Padding(grid, (1, frame.padding))
