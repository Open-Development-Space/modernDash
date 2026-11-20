"""Seven-day forecast: icon, day, rain chance, low, range bar, high."""
from __future__ import annotations

from datetime import datetime

from rich.console import Group
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from dashlib import Frame, Module
from dashlib.weather import describe, service

CONDITION_ICONS = {
    "clear": "☼",
    "night": "◐",
    "partly": "🌤",
    "cloud": "☁",
    "rain": "🌧",
    "snow": "❄",
    "storm": "🌩",
    "fog": "🌫",
}


def range_bar(lo: float, hi: float, wmin: float, wmax: float, width: int) -> str:
    """A bar covering [lo, hi], positioned within the week's [wmin, wmax] range."""
    span = max(wmax - wmin, 1)
    a = round((lo - wmin) / span * (width - 1))
    b = round((hi - wmin) / span * (width - 1))
    return "░" * a + "█" * (b - a + 1) + "░" * (width - 1 - b)


class Weekly(Module):
    name = "weekly"
    title = "7-day forecast"
    description = "Seven-day forecast with temperature range bars."
    sizes = {"compact": (5, 4), "normal": (6, 4), "tall": (8, 4), "wide": (6, 6)}
    default_size = "normal"

    def render(self, frame: Frame):
        weather = service()
        weather.poll()
        w = weather.latest
        if w is None:
            return Padding(Text(weather.status), (1, frame.pad))
        daily = w.daily
        lows = daily["temperature_2m_min"][:7]
        highs = daily["temperature_2m_max"][:7]
        wmin, wmax = min(lows), max(highs)
        rain_chances = daily.get("precipitation_probability_max", [0] * 7)[:7]
        bar_w = max(1, frame.width - 2 * frame.pad - 28)
        spaced = frame.height >= 17  # blank row between days when there is room

        grid = Table.grid(padding=(0, 1))
        grid.add_column(width=2, no_wrap=True)                   # condition
        grid.add_column(width=5, no_wrap=True)                   # day
        grid.add_column(width=6, justify="right", no_wrap=True)  # rain chance
        grid.add_column(width=4, justify="right", no_wrap=True)  # low
        grid.add_column(no_wrap=True)                            # range bar
        grid.add_column(width=4, justify="right", no_wrap=True)  # high

        for i in range(min(7, len(lows))):
            day = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            name = "Today" if i == 0 else day.strftime("%a")
            _, kind = describe(daily["weather_code"][i])
            grid.add_row(
                CONDITION_ICONS[kind],
                name,
                f"☂  {round(rain_chances[i] or 0)}%",
                f"{round(lows[i])}°",
                range_bar(lows[i], highs[i], wmin, wmax, bar_w),
                f"{round(highs[i])}°",
            )
            if spaced and i < 6:
                grid.add_row("", "", "", "", "", "")

        return Padding(Group(Text("7-DAY FORECAST", style="bold"), Text(""), grid), (1, frame.pad))
