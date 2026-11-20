"""Mouse-operated terminal interface for adjusting dashboard module sizes."""

from __future__ import annotations

import json
import os
import re
import select
import sys
import time
from contextlib import contextmanager

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from . import MODULES, DashboardModule, module_size

_MOUSE_REPORT = re.compile(r"^\x1b\[<(\d+);(\d+);(\d+)([mM])")


@contextmanager
def mouse_reporting():
    """Enable SGR mouse clicks and restore terminal state on every exit path."""
    restore_terminal = lambda: None
    if sys.platform != "win32":
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_terminal = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        restore_terminal = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old_terminal)
    sys.stdout.write("\x1b[?1000h\x1b[?1006h")
    sys.stdout.flush()
    try:
        yield
    finally:
        sys.stdout.write("\x1b[?1000l\x1b[?1006l")
        sys.stdout.flush()
        restore_terminal()


class TerminalEvents:
    """Read keyboard bytes and SGR mouse-click reports without blocking."""

    def __init__(self) -> None:
        self.buffer = ""

    def _read_available(self) -> None:
        if sys.platform == "win32":
            import msvcrt

            while msvcrt.kbhit():
                self.buffer += msvcrt.getch().decode("latin1")
        else:
            fd = sys.stdin.fileno()
            while select.select([fd], [], [], 0)[0]:
                self.buffer += os.read(fd, 64).decode("latin1")

    def poll(self) -> tuple[str, int, int] | tuple[str, str] | None:
        self._read_available()
        if not self.buffer:
            return None
        if self.buffer.startswith("\x1b[<"):
            match = _MOUSE_REPORT.match(self.buffer)
            if match:
                self.buffer = self.buffer[match.end():]
                button, x, y = (int(match.group(i)) for i in (1, 2, 3))
                if match.group(4) == "M" and button & 3 == 0:
                    return "click", x, y
                return None
            return None
        if self.buffer.startswith("\x1b") and len(self.buffer) == 1:
            return None
        key, self.buffer = self.buffer[0], self.buffer[1:]
        return "key", key


def _module_line(config: dict, module: DashboardModule, index: int) -> str:
    row = module_size(config, module.name, "row")
    column = module_size(config, module.name, "column")
    return (
        f" {index:>2}. {module.title:<24} "
        f"Row [-] {row:>2} [+]    "
        f"Column [-] {column:>2} [+]"
    )


def _screen(config: dict) -> tuple[Group, list[str]]:
    lines = [
        "DASHBOARD LAYOUT",
        "Click [-] or [+] to resize a module. Row/column sizes are relative weights.",
        "Press S or click Save to apply; press Q or click Cancel to discard.",
        "",
    ]
    lines.extend(
        _module_line(config, module, index)
        for index, module in enumerate(MODULES, 1)
    )
    lines.extend(("", " [ Save ]     [ Cancel ]"))
    return Group(*(Text(line) for line in lines)), lines


def _apply_click(config: dict, x: int, y: int) -> str | None:
    _, lines = _screen(config)
    line_index = y - 1
    if line_index == len(lines) - 1:
        if 2 <= x <= 10:
            return "save"
        if 15 <= x <= 24:
            return "cancel"
        return None

    module_index = line_index - 4
    if not 0 <= module_index < len(MODULES):
        return None
    line = lines[line_index]
    module = MODULES[module_index]
    row_minus = line.index("[-]")
    row_plus = line.index("[+]")
    column_minus = line.index("[-]", row_plus + 3)
    column_plus = line.index("[+]", column_minus + 3)
    dimension = None
    if row_minus <= x - 1 <= row_minus + 2:
        dimension = ("row", -1)
    elif row_plus <= x - 1 <= row_plus + 2:
        dimension = ("row", 1)
    elif column_minus <= x - 1 <= column_minus + 2:
        dimension = ("column", -1)
    elif column_plus <= x - 1 <= column_plus + 2:
        dimension = ("column", 1)
    if dimension is None:
        return None

    key, change = dimension
    sizes = config.setdefault("layout", {}).setdefault("modules", {})
    size = module_size(config, module.name, key)
    sizes.setdefault(module.name, {})[key] = max(1, min(12, size + change))
    return None


def edit_layout(config: dict, config_path: str, console: Console | None = None) -> bool:
    """Show the mouse-driven layout editor; return True when changes are saved."""
    console = console or Console()
    events = TerminalEvents()
    saved = False
    with mouse_reporting(), Live(
        console=console, screen=True, auto_refresh=False
    ) as live:
        while True:
            renderable, _ = _screen(config)
            live.update(renderable, refresh=True)
            event = events.poll()
            if event is None:
                time.sleep(0.02)
                continue
            if event[0] == "key":
                key = event[1].lower()
                if key == "s":
                    saved = True
                    break
                if key in ("q", "\x03"):
                    break
            elif event[0] == "click":
                result = _apply_click(config, event[1], event[2])
                if result == "save":
                    saved = True
                    break
                if result == "cancel":
                    break

    if saved:
        temporary_path = config_path + ".tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as file:
                json.dump(config, file, indent=2)
                file.write("\n")
            os.replace(temporary_path, config_path)
        except OSError:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
            raise
    return saved
