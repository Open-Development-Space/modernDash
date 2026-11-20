"""Editing model behind the layout editor (no UI code, so it is easy to test)."""
from __future__ import annotations

import copy

from .module_api import Module
from .registry import Placement, parse_layout


class EditorState:
    """A grid plus placements, with validated move / resize / add / remove."""

    def __init__(self, layout: dict, registry: dict[str, type[Module]]) -> None:
        self.registry = registry
        self.rows, self.cols, self.placements, self.warnings = parse_layout(copy.deepcopy(layout))
        self.selected: str | None = None
        self.dirty = False

    # -- queries ------------------------------------------------------------
    def get(self, pid: str | None) -> Placement | None:
        return next((p for p in self.placements if p.id == pid), None)

    def at(self, row: int, col: int) -> Placement | None:
        return next((p for p in self.placements
                     if p.row <= row < p.row + p.rows and p.col <= col < p.col + p.cols), None)

    def allowed_sizes(self, placement: Placement) -> list[tuple[str, int, int]]:
        """``(label, rows, cols)`` for each size the module offers (current size if unknown)."""
        cls = self.registry.get(placement.module)
        if cls is None:
            return [("current", placement.rows, placement.cols)]
        return [(label, r, c) for label, (r, c) in cls.sizes.items()]

    def size_label(self, placement: Placement) -> str:
        for label, r, c in self.allowed_sizes(placement):
            if (r, c) == (placement.rows, placement.cols):
                return label
        return "custom"

    def fits(self, row: int, col: int, rows: int, cols: int, ignore: str | None = None) -> bool:
        """True if the block is inside the grid and free of other placements."""
        if row < 0 or col < 0 or rows < 1 or cols < 1 or row + rows > self.rows or col + cols > self.cols:
            return False
        probe = Placement("_probe", "", row, col, rows, cols)
        return not any(p.id != ignore and p.overlaps(probe) for p in self.placements)

    # -- edits --------------------------------------------------------------
    def add(self, module: str) -> Placement | None:
        """Place a module in the first free spot, trying its default size first."""
        cls = self.registry.get(module)
        if cls is None:
            return None
        default = cls.size_for()
        sizes = [default] + sorted((s for s in cls.sizes.values() if s != default), key=lambda s: s[0] * s[1])
        for rows, cols in sizes:
            for row in range(self.rows - rows + 1):
                for col in range(self.cols - cols + 1):
                    if self.fits(row, col, rows, cols):
                        base, n = module, 2
                        ids = {p.id for p in self.placements}
                        pid = base
                        while pid in ids:
                            pid, n = f"{base}_{n}", n + 1
                        placement = Placement(pid, module, row, col, rows, cols)
                        self.placements.append(placement)
                        self.selected, self.dirty = pid, True
                        return placement
        return None

    def remove(self, pid: str) -> bool:
        placement = self.get(pid)
        if placement is None:
            return False
        self.placements.remove(placement)
        if self.selected == pid:
            self.selected = None
        self.dirty = True
        return True

    def move(self, pid: str, row: int, col: int) -> bool:
        p = self.get(pid)
        if p is None or not self.fits(row, col, p.rows, p.cols, ignore=pid):
            return False
        if (p.row, p.col) != (row, col):
            p.row, p.col, self.dirty = row, col, True
        return True

    def resize(self, pid: str, rows: int, cols: int) -> bool:
        p = self.get(pid)
        if p is None or not self.fits(p.row, p.col, rows, cols, ignore=pid):
            return False
        if (p.rows, p.cols) != (rows, cols):
            p.rows, p.cols, self.dirty = rows, cols, True
        return True

    def nearest_size(self, pid: str, want_rows: int, want_cols: int) -> tuple[int, int] | None:
        """The allowed size closest to the wanted one that fits where the module is."""
        p = self.get(pid)
        if p is None:
            return None
        options = [(r, c) for _, r, c in self.allowed_sizes(p) if self.fits(p.row, p.col, r, c, ignore=pid)]
        if not options:
            return None
        return min(options, key=lambda s: abs(s[0] - want_rows) + abs(s[1] - want_cols))

    def cycle_size(self, pid: str, step: int = 1) -> bool:
        p = self.get(pid)
        if p is None:
            return False
        sizes = [(r, c) for _, r, c in self.allowed_sizes(p)]
        start = sizes.index((p.rows, p.cols)) if (p.rows, p.cols) in sizes else -1
        for i in range(1, len(sizes) + 1):
            r, c = sizes[(start + step * i) % len(sizes)]
            if self.fits(p.row, p.col, r, c, ignore=pid):
                return self.resize(pid, r, c)
        return False

    def set_grid(self, rows: int, cols: int) -> bool:
        """Change grid dimensions; refused if a placement would fall outside."""
        if rows < 1 or cols < 1 or rows > 40 or cols > 40:
            return False
        if any(p.row + p.rows > rows or p.col + p.cols > cols for p in self.placements):
            return False
        if (rows, cols) != (self.rows, self.cols):
            self.rows, self.cols, self.dirty = rows, cols, True
        return True

    def load(self, layout: dict) -> None:
        self.rows, self.cols, self.placements, self.warnings = parse_layout(copy.deepcopy(layout))
        self.selected, self.dirty = None, True

    def to_layout(self) -> dict:
        return {
            "grid": {"rows": self.rows, "cols": self.cols},
            "modules": [p.to_json() for p in sorted(self.placements, key=lambda p: (p.row, p.col))],
        }
