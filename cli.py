#!/usr/bin/env python3
"""The ``modernDash`` command."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

HELP = """\
modernDash - a modular terminal dashboard

Usage: modernDash <command> [options]

Commands:
  run                          Start the dashboard (default when no command is given)
  config ...                   Read or change settings   (modernDash config --help)
  layout                       Open the layout editor     (same as: config layout)
  modules                      List the modules found in modules/
  install [--no-venv] [--startup[=login|shell]]
                               Set up the 'modernDash' command (and optionally startup)
  uninstall [--purge]          Remove the command and any startup entries
  startup enable [login|shell] Run the dashboard at login, or in every new terminal
  startup disable | status
  version                      Print the version
"""


def _modules() -> int:
    from dashlib.registry import discover
    registry, errors = discover()
    for name, cls in sorted(registry.items()):
        sizes = ", ".join(f"{label} {r}x{c}" for label, (r, c) in cls.sizes.items())
        print(f"{name:<12} {cls.description}\n{'':<12} sizes (rows x cols): {sizes}")
    for filename, error in errors.items():
        print(f"! {filename} failed to load: {error}", file=sys.stderr)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0].lower() if args else "run"
    rest = args[1:]

    if command in ("-h", "--help", "help"):
        print(HELP)
        return 0
    if command == "run":
        import main as dashboard
        dashboard.main()
        return 0
    if command == "config":
        import config_cli
        return config_cli.run(rest)
    if command == "layout":
        from layout_editor import run_editor
        return run_editor()
    if command == "modules":
        return _modules()
    if command in ("install", "uninstall", "startup"):
        import installer
        return installer.run(command, rest)
    if command in ("version", "--version", "-v"):
        from dashlib.config import load_config
        print(f"modernDash {load_config()['version']}")
        return 0
    print(f"Unknown command: {command}\n\n{HELP}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
