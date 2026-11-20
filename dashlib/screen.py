"""Draws placements onto the terminal.

Each module is rendered at the exact size of its grid block and the blocks
are stitched together line by line, so modules can be placed anywhere (not
just in a nested split tree).
"""
from __future__ import annotations

from datetime import datetime

from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.segment import Segment
from rich.text import Text

from .module_api import Frame, Module
from .registry import Placement


def edges(total: int, parts: int) -> list[int]:
    """Cut ``total`` characters into ``parts`` nearly equal pieces (boundaries)."""
    return [round(i * total / parts) for i in range(parts + 1)]


def cell_rect(placement: Placement, xs: list[int], ys: list[int]) -> tuple[int, int, int, int]:
    """``(x, y, width, height)`` in characters of a placement."""
    x0, x1 = xs[placement.col], xs[placement.col + placement.cols]
    y0, y1 = ys[placement.row], ys[placement.row + placement.rows]
    return x0, y0, x1 - x0, y1 - y0


class Screen:
    """A set of ``(x, y, width, height, renderable)`` tiles drawn as one block."""

    def __init__(self, width: int, height: int, tiles: list[tuple[int, int, int, int, RenderableType]]) -> None:
        self.width, self.height, self.tiles = width, height, tiles

    @staticmethod
    def _lines(console: Console, options: ConsoleOptions, renderable: RenderableType,
               w: int, h: int) -> list[list[Segment]]:
        sized = options.update_dimensions(w, h)
        try:
            return console.render_lines(renderable, sized, pad=True)
        except Exception as error:  # a module that fails while drawing must not kill the screen
            message = Text(f"{type(error).__name__}: {error}", style="dim red", no_wrap=True, overflow="crop")
            return console.render_lines(message, sized, pad=True)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        rows: list[list[tuple[int, list[Segment], int]]] = [[] for _ in range(self.height)]
        for x, y, w, h, renderable in self.tiles:
            for i, line in enumerate(self._lines(console, options, renderable, w, h)):
                if 0 <= y + i < self.height:
                    rows[y + i].append((x, line, w))
        for y, pieces in enumerate(rows):
            cursor = 0
            for x, line, w in sorted(pieces, key=lambda p: p[0]):
                if x < cursor:  # overlapping tile: first one wins
                    continue
                if x > cursor:
                    yield Segment(" " * (x - cursor))
                yield from line
                cursor = x + w
            if cursor < self.width:
                yield Segment(" " * (self.width - cursor))
            if y < self.height - 1:
                yield Segment.line()


def draw(console: Console, width: int, height: int, grid_rows: int, grid_cols: int,
         placements: list[Placement], instances: dict[str, Module], config: dict,
         now: datetime | None = None) -> Screen:
    """Render every placed module at its block size and return the combined screen."""
    now = now or datetime.now()
    pad = int(config.get("appearance", {}).get("padding", 3))
    xs, ys = edges(width, grid_cols), edges(height, grid_rows)
    tiles = []
    for placement in placements:
        x, y, w, h = cell_rect(placement, xs, ys)
        if w <= 0 or h <= 0:
            continue
        instance = instances.get(placement.id)
        if instance is None:
            renderable: RenderableType = Text(f"unknown module '{placement.module}'", style="dim red")
        else:
            frame = Frame(now=now, width=w, height=h, rows=placement.rows, cols=placement.cols,
                          pad=pad, config=config)
            try:
                renderable = instance.render(frame)
            except Exception as error:
                renderable = Text(f"{placement.module}: {type(error).__name__}: {error}", style="dim red")
        tiles.append((x, y, w, h, renderable))
    return Screen(width, height, tiles)
