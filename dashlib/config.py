"""Configuration: defaults, loading, saving and dotted-key helpers."""
from __future__ import annotations

import json
import os
import tempfile

CONFIG_FILE = "startup.json"


def app_dir() -> str:
    """Folder that holds main.py, modules/ and dbfonts/."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config_path() -> str:
    return os.path.join(app_dir(), CONFIG_FILE)


# The default layout: a 12 x 14 grid. Each entry places one module.
# "module" is the file name (without .py) inside modules/; "rows"/"cols" are
# the size in grid cells; "options" override that module's own settings.
DEFAULT_LAYOUT = {
    "grid": {"rows": 12, "cols": 14},
    "modules": [
        {"id": "status_bar", "module": "status_bar", "row": 0, "col": 0, "rows": 1, "cols": 10},
        {"id": "clock", "module": "clock", "row": 0, "col": 10, "rows": 1, "cols": 4},
        {"id": "welcome", "module": "welcome", "row": 1, "col": 0, "rows": 3, "cols": 10},
        {"id": "aquarium", "module": "aquarium", "row": 4, "col": 0, "rows": 7, "cols": 10},
        {"id": "weekly", "module": "weekly", "row": 1, "col": 10, "rows": 6, "cols": 4},
        {"id": "day", "module": "day", "row": 7, "col": 10, "rows": 4, "cols": 4},
        {"id": "updated", "module": "updated", "row": 11, "col": 0, "rows": 1, "cols": 14},
    ],
}

DEFAULT_CONFIG = {
    "version": "v1.1.4",
    "name": "",  # empty (or "USER") = use the operating-system user name
    "location": {
        "name": "New York City, NY",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "auto_from_ip": True,
    },
    "appearance": {
        "padding": 3,
        "frame_seconds": 0.25,
        "show_welcome_summary": False,
        "font_file": "dbfonts/Georgia11.json",
        "custom_font_gap": 0,
    },
    "weather": {
        "refresh_seconds": 120,
        "retry_seconds": 60,
        "rain_min_chance": 30,
        "rain_min_amount": 0.01,
        "rain_full": 0.25,
    },
    "aquarium": {"wave": " "},
    "greetings": {
        "morning": ["Good morning", "Rise and shine", "Morning, {name}", "Hey {name}"],
        "afternoon": ["Good afternoon", "Hello, {name}", "Afternoon, {name}"],
        "evening": ["Good evening, {name}", "Evening, {name}.", "Welcome back.", "Hello, {name}."],
        "night": ["Still up, {name}?", "Late night, {name}.", "Hello, {name}."],
    },
    "layout": DEFAULT_LAYOUT,
}


def merge_config(default: dict, override: dict) -> dict:
    """Merge a user config over defaults without losing nested keys."""
    result = dict(default)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result


def _read_user_file() -> dict:
    for path in (config_path(), CONFIG_FILE):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError, TypeError):
            break
    return {}


def load_config() -> dict:
    """Defaults merged with whatever is in startup.json."""
    return merge_config(DEFAULT_CONFIG, _read_user_file())


def write_user_file(data: dict) -> None:
    """Write the user's overrides atomically."""
    path = config_path()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".startup-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def set_user_value(dotted_key: str, value) -> None:
    """Store one setting in startup.json (only the user's overrides are kept there)."""
    data = _read_user_file()
    set_config_value(data, dotted_key, value)
    write_user_file(data)


def save_layout(layout: dict) -> None:
    set_user_value("layout", layout)


def reset_user_file() -> None:
    if os.path.isfile(config_path()):
        os.remove(config_path())


def get_config_value(config: dict, dotted_key: str):
    value = config
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(dotted_key)
        value = value[part]
    return value


def set_config_value(config: dict, dotted_key: str, value) -> None:
    parts = dotted_key.split(".")
    target = config
    for part in parts[:-1]:
        if not isinstance(target.get(part), dict):
            target[part] = {}
        target = target[part]
    target[parts[-1]] = value


def parse_config_value(current, raw: str):
    if current is None:
        return raw
    if isinstance(current, bool):
        normalized = raw.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
        raise ValueError("use true/false, yes/no, or 1/0")
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    if isinstance(current, str):
        return raw
    return json.loads(raw)
