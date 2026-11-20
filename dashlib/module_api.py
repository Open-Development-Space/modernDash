"""The contract between the dashboard and a module.

A module is one ``.py`` file in ``modules/`` that defines a subclass of
``Module``. The host only ever talks to modules through this interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rich.console import RenderableType


@dataclass(frozen=True)
class Frame:
    """Everything a module needs to draw one frame of itself."""

    now: datetime
    width: int            # characters available to this module
    height: int           # lines available to this module
    rows: int             # size of the module's cell block, in grid cells
    cols: int
    pad: int              # horizontal padding from appearance.padding
    config: dict = field(default_factory=dict, repr=False)  # whole config, read-only

    @property
    def vpad(self) -> int:
        """1 when a single-line module has a spare row above/below, else 0."""
        return 1 if self.height >= 3 else 0


class Module:
    """Base class for dashboard modules.

    Class attributes a module may set:

    ``name``            id used in the layout config (defaults to the file name)
    ``title``           friendly name shown in the layout editor
    ``description``     one-line help text
    ``sizes``           size variations as ``{label: (rows, cols)}`` in grid cells
    ``default_size``    label used when the editor adds the module
    ``config_section``  top-level config section whose keys feed ``option()``
    ``defaults``        fallback values for ``option()``

    One instance is created per placement, so instance attributes are free to
    hold animation state.
    """

    name: str = ""
    title: str = ""
    description: str = ""
    sizes: dict[str, tuple[int, int]] = {"default": (1, 1)}
    default_size: str = ""
    config_section: str = ""
    defaults: dict[str, Any] = {}

    def __init__(self, options: dict | None = None, config: dict | None = None) -> None:
        self.options = dict(options or {})
        self.config = config or {}

    def option(self, key: str, default: Any = None) -> Any:
        """Placement option, else the config section, else the class default."""
        if key in self.options:
            return self.options[key]
        section = self.config.get(self.config_section) if self.config_section else None
        if isinstance(section, dict) and key in section:
            return section[key]
        return self.defaults.get(key, default)

    def render(self, frame: Frame) -> RenderableType:  # pragma: no cover - interface
        raise NotImplementedError

    @classmethod
    def size_for(cls, label: str | None = None) -> tuple[int, int]:
        label = label or cls.default_size or next(iter(cls.sizes))
        return cls.sizes.get(label) or next(iter(cls.sizes.values()))
