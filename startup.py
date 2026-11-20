#!/usr/bin/env python3
"""Application entry point, configuration, weather service, and module composer."""
from __future__ import annotations

import getpass
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from urllib.request import urlopen

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.text import Text

from modules import DEFAULT_MODULE_SIZES, module_size
from modules import clock, current, footer, forecast, status_bar
from modules.aquarium import Aquarium
from modules.context import Frame, Geometry
from modules.layout_editor import edit_layout
from modules.terminal import KeyWatcher
from modules.welcome import Welcome
from modules.weather_display import SNOW_CODES

# =============================================================================
# 1. CONFIGURATION
# =============================================================================

CONFIG_FILE = "startup.json"

DEFAULT_CONFIG = {
    "version": "v0.2.2",
    "name": "USER",
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
    "layout": {
        "modules": {
            name: dict(size) for name, size in DEFAULT_MODULE_SIZES.items()
        },
    },
    "weather": {
        "refresh_seconds": 120,
        "retry_seconds": 60,
        "rain_min_chance": 30,
        "rain_min_amount": 0.01,
        "rain_full": 0.25,
    },
    "aquarium": {
        "wave": " ",
    },
    "greetings": {
        "morning": [
            "Good morning", 
            "Rise and shine", 
            "Morning, {name}", 
            "Hey {name}"
        ],
        "afternoon": [
            "Good afternoon", 
            "Hello, {name}", 
            "Afternoon, {name}"
        ],
        "evening": [
            "Good evening, {name}", 
            "Evening, {name}.", 
            "Welcome back.", 
            "Hello, {name}."
        ],
        "night": [
            "Still up, {name}?", 
            "Late night, {name}.", 
            "Hello, {name}."
        ]
    },
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


def load_dashboard_config() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    paths = (os.path.join(here, CONFIG_FILE), CONFIG_FILE)
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                override = json.load(f)
            if isinstance(override, dict):
                return merge_config(DEFAULT_CONFIG, override)
        except (OSError, json.JSONDecodeError, TypeError):
            break
    return merge_config(DEFAULT_CONFIG, {})


def location_from_ip(timeout: float = 5.0) -> tuple[str, float, float] | None:
    """Resolve a public IP location without requiring an API key."""
    try:
        url = "http://ip-api.com/json/?fields=status,message,country,regionName,city,lat,lon"
        with urlopen(url, timeout=timeout) as response:
            data = json.load(response)
        if data.get("status") != "success":
            return None
        city = str(data.get("city") or "").strip()
        region = str(data.get("regionName") or "").strip()
        name = ", ".join(part for part in (city, region) if part)
        if not name:
            name = str(data.get("country") or "Unknown location")
        return name, float(data["lat"]), float(data["lon"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None

def name_from_user():
    username = getpass.getuser()
    return username.title()


CONFIG = load_dashboard_config()

GREETING_NAME = str(name_from_user())
LOCATION_NAME = str(CONFIG["location"]["name"])
LAT = float(CONFIG["location"]["latitude"])
LON = float(CONFIG["location"]["longitude"])
if CONFIG["location"]["auto_from_ip"]:
    detected = location_from_ip()
    if detected:
        LOCATION_NAME, LAT, LON = detected

REFRESH_SECONDS = int(CONFIG["weather"]["refresh_seconds"])
RETRY_SECONDS = int(CONFIG["weather"]["retry_seconds"])
RAIN_MIN_CHANCE = int(CONFIG["weather"]["rain_min_chance"])
RAIN_MIN_AMOUNT = float(CONFIG["weather"]["rain_min_amount"])
RAIN_FULL = float(CONFIG["weather"]["rain_full"])

PAD = int(CONFIG["appearance"]["padding"])
FRAME_SECONDS = float(CONFIG["appearance"]["frame_seconds"])
SHOW_WELCOME_SUMMARY = bool(CONFIG["appearance"]["show_welcome_summary"])
FONT_FILE = CONFIG["appearance"]["font_file"] or None
CUSTOM_FONT_GAP = int(CONFIG["appearance"]["custom_font_gap"])
WAVE = str(CONFIG["aquarium"]["wave"])
GREETINGS = CONFIG["greetings"]


ISO_MINUTE = "%Y-%m-%dT%H:%M"


def header_height(config: dict = CONFIG) -> int:
    return 3 * (
        module_size(config, "status_bar", "row")
        + module_size(config, "clock", "row")
    ) // 2


# =============================================================================
# WEATHER SERVICE
# =============================================================================

@dataclass(frozen=True)
class RainHour:
    """One upcoming hour. ``amount`` is 0.0 unless the hour counts as wet."""

    time: datetime
    amount: float   # inches
    snow: bool


class Weather:
    """A parsed Open-Meteo response plus values derived from it.

    Attributes:
        current:    the "current" block (temperature, humidity, ...)
        daily:      the "daily" block (7 days of highs, lows, sunrise, ...)
        hourly:     the "hourly" block (precipitation per hour)
        fetched_at: when the data was downloaded (local clock)
        now:        "now" according to the API, in the location's time zone
        rain:       the next 24 hours as a list of ``RainHour``
    """

    def __init__(self, raw: dict, fetched_at: datetime) -> None:
        for key in ("current", "daily", "hourly"):
            if key not in raw:
                raise ValueError(f"missing '{key}' in API response")
        self.current = raw["current"]
        self.daily = raw["daily"]
        self.hourly = raw["hourly"]
        self.fetched_at = fetched_at
        self.now = datetime.strptime(self.current["time"], ISO_MINUTE)
        self.rain = self._rain_window(24)

    def _rain_window(self, count: int) -> list[RainHour]:
        start = self.now.replace(minute=0)  # top of the current hour
        hours: list[RainHour] = []
        for i, stamp in enumerate(self.hourly["time"]):
            when = datetime.strptime(stamp, ISO_MINUTE)
            if when < start:
                continue
            if len(hours) == count:
                break
            amount = self.hourly["precipitation"][i] or 0.0
            chance = self.hourly["precipitation_probability"][i] or 0
            wet = chance >= RAIN_MIN_CHANCE and amount >= RAIN_MIN_AMOUNT
            snow = self.hourly["weather_code"][i] in SNOW_CODES
            hours.append(RainHour(when, amount if wet else 0.0, snow))
        return hours

    def rain_outlook(self) -> str:
        """One-line summary such as ``Rain starting 3 PM`` or ``Rain until 4 PM``."""
        hours = self.rain
        if not hours:
            return ""
        today: date = self.now.date()

        def stamp(h: RainHour) -> str:
            s = h.time.strftime("%I %p").lstrip("0")
            return s if h.time.date() == today else f"tomorrow {s}"

        wet = [h.amount > 0 for h in hours]
        if not any(wet):
            return "No rain expected for the next 24 hours"
        first = wet.index(True)
        kind = "Snow" if hours[first].snow else "Rain"
        if first == 0:  # already wet this hour: find when it stops
            dry = next((i for i, w in enumerate(wet) if not w), None)
            if dry is None:
                return f"{kind} for the next 24 hours"
            return f"{kind} until {stamp(hours[dry])}"
        return f"{kind} starting {stamp(hours[first])}"


API_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather_json() -> dict:
    """Download current + daily + hourly data (blocking; call from a thread)."""
    url = (
        f"{API_URL}?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        "weather_code,wind_speed_10m,is_day"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,sunrise,sunset,uv_index_max"
        "&hourly=precipitation_probability,precipitation,weather_code"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch"
        "&timezone=auto&forecast_days=7"
    )
    with urlopen(url, timeout=5) as response:
        return json.load(response)


class WeatherService:
    """Fetches weather in a background thread so the UI never blocks.

    Call ``poll()`` every frame: it starts a fetch when one is due. Read the
    newest successful result from ``latest`` (``None`` until the first fetch
    succeeds). If a refresh fails, the previous data is kept and ``failing``
    turns True until a later fetch succeeds.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: Weather | None = None
        self._failing = False
        self._next_fetch = 0.0
        self._thread: threading.Thread | None = None

    @property
    def latest(self) -> Weather | None:
        with self._lock:
            return self._latest

    @property
    def failing(self) -> bool:
        with self._lock:
            return self._failing

    @property
    def status(self) -> str:
        """Message shown in place of weather data when there is none yet."""
        return "Weather unavailable, retrying…" if self.failing else "Loading weather…"

    def poll(self) -> None:
        """Start a background fetch if one is due and none is running."""
        busy = self._thread is not None and self._thread.is_alive()
        if not busy and time.time() >= self._next_fetch:
            self._thread = threading.Thread(target=self._fetch, daemon=True)
            self._thread.start()

    def _fetch(self) -> None:
        try:
            weather = Weather(fetch_weather_json(), datetime.now())
        except Exception:  # network, JSON or schema problem: keep old data, retry soon
            with self._lock:
                self._failing = True
            self._next_fetch = time.time() + RETRY_SECONDS
            return
        with self._lock:
            self._latest = weather
            self._failing = False
        self._next_fetch = time.time() + REFRESH_SECONDS


# =============================================================================
# DASHBOARD COMPOSITION
# =============================================================================

def build_layout(config: dict = CONFIG) -> Layout:
    header_h = header_height(config)
    footer_h = module_size(config, "footer", "row")
    root = Layout(name="root")
    root.split_column(
        Layout(name="header", size=header_h),
        Layout(name="body"),
        Layout(name="footer_area", size=footer_h),
    )
    root["header"].split_row(
        Layout(name="status_bar", ratio=module_size(config, "status_bar", "column")),
        Layout(name="time", ratio=module_size(config, "clock", "column")),
    )
    left_column = (
        module_size(config, "welcome", "column")
        + module_size(config, "aquarium", "column")
    )
    right_column = (
        module_size(config, "forecast", "column")
        + module_size(config, "current", "column")
    )
    root["body"].split_row(
        Layout(name="left", ratio=max(1, left_column // 2)),
        Layout(name="right", ratio=max(1, right_column // 2)),
    )
    root["left"].split_column(
        Layout(name="welcome", ratio=module_size(config, "welcome", "row")),
        Layout(name="main", ratio=module_size(config, "aquarium", "row")),
    )
    root["right"].split_column(
        Layout(name="weekly", ratio=module_size(config, "forecast", "row")),
        Layout(name="day", ratio=module_size(config, "current", "row")),
    )
    footer_column = module_size(config, "footer", "column")
    root["footer_area"].split_row(
        Layout(name="footer_spacer", ratio=max(1, 13 - footer_column)),
        Layout(name="footer", ratio=footer_column),
    )
    root["footer_spacer"].update(Text(""))
    return root


def dashboard_geometry(cols: int, lines: int, config: dict = CONFIG) -> Geometry:
    left_column = (
        module_size(config, "welcome", "column")
        + module_size(config, "aquarium", "column")
    )
    right_column = (
        module_size(config, "forecast", "column")
        + module_size(config, "current", "column")
    )
    left_ratio = max(1, left_column // 2)
    right_ratio = max(1, right_column // 2)
    right_width = cols * right_ratio // (left_ratio + right_ratio)
    body_height = lines - header_height(config) - module_size(config, "footer", "row")
    forecast_rows = module_size(config, "forecast", "row")
    current_rows = module_size(config, "current", "row")
    return Geometry(
        cols=cols,
        lines=lines,
        left_inner=cols - right_width - 2 * PAD,
        right_inner=right_width - 2 * PAD,
        body_h=body_height,
        day_h=body_height * current_rows // (forecast_rows + current_rows),
    )


class Dashboard:
    """Poll shared services and compose self-contained dashboard modules."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(style="white")
        self.layout = build_layout()
        self.weather = WeatherService()
        self.aquarium = Aquarium(WAVE)
        self.welcome = Welcome(
            FONT_FILE,
            CUSTOM_FONT_GAP,
            GREETINGS,
            GREETING_NAME,
            SHOW_WELCOME_SUMMARY,
        )

    def update(self) -> None:
        self.weather.poll()
        weather = self.weather.latest
        frame = Frame(
            now=datetime.now(),
            geo=dashboard_geometry(self.console.width, self.console.height),
            weather=weather,
            status=self.weather.status,
            stale=weather is not None and self.weather.failing,
            padding=PAD,
            location=LOCATION_NAME,
            version=DEFAULT_CONFIG["version"],
            rain_full=RAIN_FULL,
        )
        welcome, welcome_content_h = self.welcome.render(frame)
        welcome_h = max(
            1,
            round(
                welcome_content_h
                * module_size(CONFIG, "welcome", "row")
                / DEFAULT_MODULE_SIZES["welcome"]["row"]
                * DEFAULT_MODULE_SIZES["aquarium"]["row"]
                / module_size(CONFIG, "aquarium", "row")
            ),
        )
        self.layout["status_bar"].update(status_bar.render(frame, self.welcome.font_note))
        self.layout["time"].update(clock.render(frame))
        self.layout["footer"].update(footer.render(frame))
        self.layout["welcome"].size = welcome_h
        self.layout["welcome"].update(welcome)
        self.layout["main"].update(self.aquarium.render(frame, welcome_h))
        self.layout["weekly"].update(forecast.render(frame))
        self.layout["day"].update(current.render(frame))

    def run(self) -> None:
        with KeyWatcher() as keys, Live(
            self.layout, console=self.console, screen=True, auto_refresh=False
        ) as live:
            while not keys.pressed():
                self.update()
                live.refresh()
                time.sleep(FRAME_SECONDS)


def config_file_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, CONFIG_FILE)


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
    if isinstance(current, list):
        return json.loads(raw)
    return json.loads(raw)


def resolve_font_name(raw: str) -> str:
    raw = raw.strip()
    if raw.lower() in ("none", "default", "builtin", "built-in"):
        return None

    here = os.path.dirname(os.path.abspath(__file__))
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


def print_config_help() -> None:
    print(
        "Usage:\n"
        "  python startup.py config <tool> <value>\n"
        "  python startup.py config <section.key> <value>\n"
        "\n"
        "Tools:\n"
        "  font / font_file       Greeting font (a dbfonts filename or path)\n"
        "  font_gap               Space between custom-font characters\n"
        "  padding                Left/right dashboard padding\n"
        "  frame_seconds          Animation frame delay\n"
        "  welcome_summary        true/false\n"
        "  name                   User/greeting name\n"
        "  location               Location display name\n"
        "  latitude               Location latitude\n"
        "  longitude              Location longitude\n"
        "  auto_location          true/false; detect location from public IP\n"
        "  refresh_seconds        Weather refresh interval\n"
        "  retry_seconds          Weather retry interval\n"
        "  rain_min_chance        Rain chance threshold\n"
        "  rain_min_amount        Minimum rain amount\n"
        "  rain_full              Rain amount for full bar\n"
        "  wave                   Aquarium wave character\n"
        "\n"
        "Commands:\n"
        "  config list            Print the effective configuration\n"
        "  config get <key>       Print one setting\n"
        "  config fonts           List available font files\n"
        "  config layout           Open the mouse-driven layout editor\n"
        "  config reset           Remove startup.json and restore defaults\n"
    )


def config():
    args = sys.argv[2:]
    if not args or args[0].lower() in ("help", "-h", "--help"):
        print_config_help()
        return

    command = args[0].lower()
    current = load_dashboard_config()

    if command == "list":
        print(json.dumps(current, indent=2))
        return

    if command == "layout":
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("The layout editor requires an interactive terminal.", file=sys.stderr)
            raise SystemExit(2)
        try:
            saved = edit_layout(current, config_file_path())
        except OSError as error:
            print(f"Could not write {config_file_path()}: {error}", file=sys.stderr)
            raise SystemExit(1)
        if saved:
            print("Dashboard layout saved.")
        return

    if command == "fonts":
        here = os.path.dirname(os.path.abspath(__file__))
        dbfonts = os.path.join(here, "dbfonts")
        fonts = (
            sorted(
                os.path.relpath(os.path.join(root, filename), here).replace("\\", "/")
                for root, _, names in os.walk(dbfonts)
                for filename in names
                if filename.lower().endswith(".json")
            )
            if os.path.isdir(dbfonts)
            else []
        )
        print("\n".join(fonts) if fonts else "No font JSON files found in dbfonts/")
        return

    if command == "reset":
        path = config_file_path()
        if os.path.isfile(path):
            os.remove(path)
        print("Configuration reset to defaults.")
        return

    if command == "get":
        if len(args) < 2:
            print("Usage: python startup.py config get <key>", file=sys.stderr)
            raise SystemExit(2)
        try:
            value = get_config_value(current, args[1])
        except KeyError as error:
            print(f"Unknown config key: {error.args[0]}", file=sys.stderr)
            raise SystemExit(2)
        print(json.dumps(value) if not isinstance(value, str) else value)
        return

    aliases = {
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

    key = aliases.get(command, command)
    if len(args) < 2:
        print("Usage: python startup.py config <tool> <value>", file=sys.stderr)
        raise SystemExit(2)

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
            raise SystemExit(2)

    set_config_value(current, key, value)
    path = config_file_path()
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(current, file, indent=2)
            file.write("\n")
    except OSError as error:
        print(f"Could not write {path}: {error}", file=sys.stderr)
        raise SystemExit(1)

    print(f"{key} = {json.dumps(value)}")


def main() -> None:
    try:
        Dashboard().run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "config":
            config()
    else:
        main()
