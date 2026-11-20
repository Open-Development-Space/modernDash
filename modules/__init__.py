"""Dashboard module definitions and layout sizing helpers."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class DashboardModule:
    name: str
    title: str
    row: int
    column: int


from . import aquarium, clock, current, footer, forecast, status_bar, welcome

MODULES: Final = (
    status_bar.MODULE,
    clock.MODULE,
    welcome.MODULE,
    aquarium.MODULE,
    forecast.MODULE,
    current.MODULE,
    footer.MODULE,
)

DEFAULT_MODULE_SIZES: Final = {
    module.name: {"row": module.row, "column": module.column}
    for module in MODULES
}


def module_size(config: dict, name: str, dimension: str) -> int:
    """Return a bounded configured size, falling back to the module default."""
    defaults = next(module for module in MODULES if module.name == name)
    fallback = getattr(defaults, dimension)
    try:
        value = config["layout"]["modules"][name][dimension]
        return max(1, min(12, int(value)))
    except (KeyError, TypeError, ValueError):
        return fallback
