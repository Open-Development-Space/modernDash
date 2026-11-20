"""Finds module files in modules/ and turns layout config into placements."""
from __future__ import annotations

import importlib.util
import inspect
import os
import sys
from dataclasses import dataclass, field

from .config import app_dir
from .module_api import Module


def modules_dir() -> str:
    return os.path.join(app_dir(), "modules")


def discover(directory: str | None = None) -> tuple[dict[str, type[Module]], dict[str, str]]:
    """Import every ``modules/*.py`` (files starting with ``_`` are skipped).

    Returns ``(registry, errors)``: ``registry`` maps a module name to its
    class, ``errors`` maps a file name to why it failed to load, so one broken
    module never takes the dashboard down.
    """
    directory = directory or modules_dir()
    if app_dir() not in sys.path:
        sys.path.insert(0, app_dir())
    registry: dict[str, type[Module]] = {}
    errors: dict[str, str] = {}
    if not os.path.isdir(directory):
        return registry, errors
    for filename in sorted(os.listdir(directory)):
        stem, ext = os.path.splitext(filename)
        if ext != ".py" or stem.startswith("_"):
            continue
        qualified = f"moderndash_modules.{stem}"
        try:
            spec = importlib.util.spec_from_file_location(qualified, os.path.join(directory, filename))
            if spec is None or spec.loader is None:
                raise ImportError("cannot load file")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[qualified] = mod
            spec.loader.exec_module(mod)
        except Exception as error:
            sys.modules.pop(qualified, None)
            errors[filename] = f"{type(error).__name__}: {error}"
            continue
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, Module) and cls is not Module and cls.__module__ == qualified:
                cls.name = cls.name or stem
                cls.title = cls.title or cls.name.replace("_", " ").title()
                registry[cls.name] = cls
    return registry, errors


@dataclass
class Placement:
    """One module placed on the grid."""

    id: str
    module: str
    row: int
    col: int
    rows: int
    cols: int
    options: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        data = {"id": self.id, "module": self.module, "row": self.row, "col": self.col,
                "rows": self.rows, "cols": self.cols}
        if self.options:
            data["options"] = self.options
        return data

    def overlaps(self, other: "Placement") -> bool:
        return not (self.row + self.rows <= other.row or other.row + other.rows <= self.row
                    or self.col + self.cols <= other.col or other.col + other.cols <= self.col)


def parse_layout(layout: dict) -> tuple[int, int, list[Placement], list[str]]:
    """Validate the ``layout`` config section.

    Returns ``(grid_rows, grid_cols, placements, warnings)``. Entries that are
    malformed, outside the grid or overlapping an earlier entry are skipped
    and reported in ``warnings`` instead of raising.
    """
    warnings: list[str] = []
    grid = layout.get("grid") if isinstance(layout, dict) else None
    grid = grid if isinstance(grid, dict) else {}
    try:
        grid_rows, grid_cols = max(1, int(grid.get("rows", 12))), max(1, int(grid.get("cols", 14)))
    except (TypeError, ValueError):
        grid_rows, grid_cols = 12, 14
        warnings.append("layout.grid is invalid; using 12 x 14")

    placements: list[Placement] = []
    used_ids: set[str] = set()
    entries = layout.get("modules", []) if isinstance(layout, dict) else []
    for index, entry in enumerate(entries if isinstance(entries, list) else []):
        try:
            module = str(entry["module"])
            row, col = int(entry["row"]), int(entry["col"])
            rows, cols = int(entry.get("rows", 1)), int(entry.get("cols", 1))
            options = entry.get("options") or {}
            if not isinstance(options, dict):
                raise TypeError("options must be an object")
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            warnings.append(f"layout.modules[{index}] skipped: {error}")
            continue
        base = str(entry.get("id") or module)
        pid, n = base, 2
        while pid in used_ids:
            pid, n = f"{base}_{n}", n + 1
        placement = Placement(pid, module, row, col, rows, cols, options)
        if rows < 1 or cols < 1 or row < 0 or col < 0 or row + rows > grid_rows or col + cols > grid_cols:
            warnings.append(f"'{pid}' does not fit the {grid_rows} x {grid_cols} grid; skipped")
            continue
        clash = next((p for p in placements if p.overlaps(placement)), None)
        if clash:
            warnings.append(f"'{pid}' overlaps '{clash.id}'; skipped")
            continue
        used_ids.add(pid)
        placements.append(placement)
    return grid_rows, grid_cols, placements, warnings
