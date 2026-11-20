#!/usr/bin/env python3
"""
modernDash host
===============

A generic full-screen dashboard runner. It knows nothing about what is on the
screen: the ``layout`` section of the config file lists which module files
from ``modules/`` to show, where, and at what size, and each module draws
itself.

    config file ──► layout ──► one module instance per placement
    every frame:  module.render(Frame) ──► stitched into one screen ──► Live

The config file is watched, so saving a new layout (for example from the
layout editor) updates a running dashboard without a restart.

Run it:  ``python main.py``  (or ``modernDash run`` once installed).
Press any key to quit.
"""
from __future__ import annotations

import os
import sys
import time

if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.live import Live

from dashlib.config import config_path, load_config
from dashlib.keys import KeyWatcher
from dashlib.registry import discover, parse_layout
from dashlib.screen import draw


class Dashboard:
    """Owns the module instances and redraws the screen every frame."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(style="white")  # all white, no borders
        self.registry, self.load_errors = discover()
        self._stamp = None
        self.reload()

    # -- configuration ------------------------------------------------------
    def reload(self) -> None:
        """(Re)build every module instance from the config file."""
        self.config = load_config()
        self._stamp = self._config_stamp()
        self.grid_rows, self.grid_cols, self.placements, self.warnings = parse_layout(
            self.config.get("layout", {})
        )
        self.instances = {}
        for placement in self.placements:
            cls = self.registry.get(placement.module)
            if cls is not None:
                self.instances[placement.id] = cls(placement.options, self.config)
        try:
            self.frame_seconds = max(0.02, float(self.config["appearance"]["frame_seconds"]))
        except (KeyError, TypeError, ValueError):
            self.frame_seconds = 0.25

    @staticmethod
    def _config_stamp():
        try:
            return os.stat(config_path()).st_mtime_ns
        except OSError:
            return None

    # -- drawing ------------------------------------------------------------
    def screen(self):
        return draw(
            self.console, self.console.width, self.console.height,
            self.grid_rows, self.grid_cols, self.placements, self.instances, self.config,
        )

    def run(self) -> None:
        """Show the dashboard full screen until any key is pressed."""
        last_check = time.monotonic()
        with KeyWatcher() as keys, Live(
            self.screen(), console=self.console, screen=True, auto_refresh=False
        ) as live:
            while not keys.pressed():
                if time.monotonic() - last_check >= 1.0:
                    last_check = time.monotonic()
                    if self._config_stamp() != self._stamp:
                        self.reload()
                live.update(self.screen(), refresh=True)
                time.sleep(self.frame_seconds)


def main() -> None:
    try:
        Dashboard().run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
