"""``modernDash config ...``: read and change settings from the command line."""
from __future__ import annotations

import json
import os
import sys

from dashlib.config import (
    app_dir, config_path, get_config_value, load_config, parse_config_value,
    reset_user_file, set_config_value, _read_user_file, write_user_file,
)

ALIASES = {
    "font": "appearance.font_file",
    "font_file": "appearance.font_file",
    "font-gap": "appearance.custom_font_gap",
    "font_gap": "appearance.custom_font_gap",
    "padding": "appearance.padding",
    "frame": "appearance.frame_seconds",
    "frame_seconds": "appearance.frame_seconds",
    "welcome_summary": "appearance.show_welcome_summary",
    "show_welcome_summary": "appearance.show_welcome_summary",
    "name": "name",
    "location": "location.name",
    "latitude": "location.latitude",
    "longitude": "location.longitude",
    "auto_location": "location.auto_from_ip",
    "auto_from_ip": "location.auto_from_ip",
    "refresh": "weather.refresh_seconds",
    "refresh_seconds": "weather.refresh_seconds",
    "retry": "weather.retry_seconds",
    "retry_seconds": "weather.retry_seconds",
    "rain_min_chance": "weather.rain_min_chance",
    "rain_min_amount": "weather.rain_min_amount",
    "rain_full": "weather.rain_full",
    "wave": "aquarium.wave",
}

HELP = """\
Usage:
  modernDash config <tool> <value>
  modernDash config <section.key> <value>

Tools:
  layout                 Open the layout editor (mouse GUI)
  font / font_file       Greeting font (a dbfonts filename or path)
  font_gap               Space between custom-font characters
  padding                Left/right padding inside each module
  frame_seconds          Animation frame delay
  welcome_summary        true/false
  name                   User/greeting name
  location               Location display name
  latitude / longitude   Location coordinates
  auto_location          true/false; detect location from public IP
  refresh_seconds        Weather refresh interval
  retry_seconds          Weather retry interval
  rain_min_chance        Rain chance threshold
  rain_min_amount        Minimum rain amount
  rain_full              Rain amount for full bar
  wave                   Aquarium wave character

Commands:
  config list            Print the effective configuration
  config get <key>       Print one setting
  config fonts           List available font files
  config reset           Remove startup.json and restore defaults
"""


def resolve_font_name(raw: str):
    raw = raw.strip()
    if raw.lower() in ("none", "default", "builtin", "built-in"):
        return ""
    here = app_dir()
    candidates = (
        raw,
        os.path.join(here, raw),
        os.path.join(here, "dbfonts", raw),
        os.path.join(here, "dbfonts", os.path.basename(raw)),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            absolute = os.path.abspath(candidate)
            try:
                return os.path.relpath(absolute, here).replace("\\", "/")
            except ValueError:
                return absolute
    return raw


def run(args: list[str]) -> int:
    if not args or args[0].lower() in ("help", "-h", "--help"):
        print(HELP)
        return 0

    command = args[0].lower()

    if command == "layout":
        from layout_editor import run_editor
        return run_editor()

    current = load_config()

    if command == "list":
        print(json.dumps(current, indent=2))
        return 0

    if command == "fonts":
        here = app_dir()
        dbfonts = os.path.join(here, "dbfonts")
        fonts = (
            sorted(
                os.path.relpath(os.path.join(root, filename), here).replace("\\", "/")
                for root, _, names in os.walk(dbfonts)
                for filename in names
                if filename.lower().endswith(".json")
            )
            if os.path.isdir(dbfonts) else []
        )
        print("\n".join(fonts) if fonts else "No font JSON files found in dbfonts/")
        return 0

    if command == "reset":
        reset_user_file()
        print("Configuration reset to defaults.")
        return 0

    if command == "get":
        if len(args) < 2:
            print("Usage: modernDash config get <key>", file=sys.stderr)
            return 2
        try:
            value = get_config_value(current, ALIASES.get(args[1], args[1]))
        except KeyError as error:
            print(f"Unknown config key: {error.args[0]}", file=sys.stderr)
            return 2
        print(value if isinstance(value, str) else json.dumps(value))
        return 0

    key = ALIASES.get(command, command)
    if len(args) < 2:
        print("Usage: modernDash config <tool> <value>", file=sys.stderr)
        return 2

    raw_value = " ".join(args[1:]).strip()
    try:
        existing = get_config_value(current, key)
    except KeyError:
        existing = None

    if key == "appearance.font_file":
        value = resolve_font_name(raw_value)
    else:
        try:
            value = parse_config_value(existing, raw_value)
        except (ValueError, json.JSONDecodeError) as error:
            print(f"Invalid value for {key}: {error}", file=sys.stderr)
            return 2

    data = _read_user_file()
    set_config_value(data, key, value)
    try:
        write_user_file(data)
    except OSError as error:
        print(f"Could not write {config_path()}: {error}", file=sys.stderr)
        return 1
    print(f"{key} = {json.dumps(value)}")
    return 0
