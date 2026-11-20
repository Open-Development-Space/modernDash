"""Weather data shared by every weather-aware module.

One background service per process (``service()``): modules call ``poll()``
each frame and read ``latest``. Because it is a singleton, five modules that
show weather still cause only one network request per refresh.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from urllib.request import urlopen

from .config import load_config

API_URL = "https://api.open-meteo.com/v1/forecast"
ISO_MINUTE = "%Y-%m-%dT%H:%M"

# WMO weather codes (as used by Open-Meteo) -> (label, art key).
SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})
WEATHER_CODES = [
    (frozenset({0}), "Clear", "clear"),
    (frozenset({1}), "Mostly clear", "clear"),
    (frozenset({2}), "Partly cloudy", "partly"),
    (frozenset({3}), "Overcast", "cloud"),
    (frozenset({45, 48}), "Fog", "fog"),
    (frozenset({51, 53, 55, 56, 57}), "Drizzle", "rain"),
    (frozenset({61, 63, 65, 66, 67}), "Rain", "rain"),
    (frozenset({80, 81, 82}), "Showers", "rain"),
    (SNOW_CODES, "Snow", "snow"),
    (frozenset({95, 96, 99}), "Thunderstorm", "storm"),
]


def describe(code: int) -> tuple[str, str]:
    """Map a WMO weather code to ``(label, art key)``."""
    for codes, label, art in WEATHER_CODES:
        if code in codes:
            return label, art
    return "Unknown", "cloud"


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

    def __init__(self, raw: dict, fetched_at: datetime,
                 min_chance: int = 30, min_amount: float = 0.01) -> None:
        for key in ("current", "daily", "hourly"):
            if key not in raw:
                raise ValueError(f"missing '{key}' in API response")
        self.current = raw["current"]
        self.daily = raw["daily"]
        self.hourly = raw["hourly"]
        self.fetched_at = fetched_at
        self.min_chance = min_chance
        self.min_amount = min_amount
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
            wet = chance >= self.min_chance and amount >= self.min_amount
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


class WeatherService:
    """Fetches weather in a background thread so the UI never blocks.

    ``poll()`` starts a fetch when one is due. ``latest`` is the newest
    successful result (``None`` until the first fetch succeeds). If a refresh
    fails the previous data is kept and ``failing`` is True until a later
    fetch succeeds. The IP-based location lookup also happens in the thread.
    """

    def __init__(self, config: dict) -> None:
        loc, weather = config["location"], config["weather"]
        self._lock = threading.Lock()
        self._location = (str(loc["name"]), float(loc["latitude"]), float(loc["longitude"]))
        self._auto_location = bool(loc["auto_from_ip"])
        self.refresh_seconds = int(weather["refresh_seconds"])
        self.retry_seconds = int(weather["retry_seconds"])
        self.min_chance = int(weather["rain_min_chance"])
        self.min_amount = float(weather["rain_min_amount"])
        self._latest: Weather | None = None
        self._failing = False
        self._next_fetch = 0.0
        self._thread: threading.Thread | None = None

    @property
    def location_name(self) -> str:
        with self._lock:
            return self._location[0]

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

    def _download(self) -> dict:
        _, lat, lon = self._location
        url = (
            f"{API_URL}?latitude={lat}&longitude={lon}"
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

    def _fetch(self) -> None:
        if self._auto_location:
            self._auto_location = False  # try once; fall back to the configured place
            detected = location_from_ip()
            if detected:
                with self._lock:
                    self._location = detected
        try:
            weather = Weather(self._download(), datetime.now(), self.min_chance, self.min_amount)
        except Exception:  # network, JSON or schema problem: keep old data, retry soon
            with self._lock:
                self._failing = True
            self._next_fetch = time.time() + self.retry_seconds
            return
        with self._lock:
            self._latest = weather
            self._failing = False
        self._next_fetch = time.time() + self.refresh_seconds


_service: WeatherService | None = None
_service_lock = threading.Lock()


def service() -> WeatherService:
    """The shared weather service (created on first use from the config file)."""
    global _service
    with _service_lock:
        if _service is None:
            _service = WeatherService(load_config())
        return _service
