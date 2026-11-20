from datetime import datetime

from rich.console import Group
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from . import DashboardModule
from .context import Frame
from .weather_display import CONDITION_ICONS, describe

MODULE = DashboardModule("forecast", "7-day forecast", row=3, column=2)


def _placeholder(frame: Frame):
    return Padding(Text(frame.status), (1, frame.padding))


def _range_bar(lo: float, hi: float, wmin: float, wmax: float, width: int) -> str:
    span = max(wmax - wmin, 1)
    a = round((lo - wmin) / span * (width - 1))
    b = round((hi - wmin) / span * (width - 1))
    return "░" * a + "█" * (b - a + 1) + "░" * (width - 1 - b)


def render(frame: Frame):
    weather = frame.weather
    if weather is None:
        return _placeholder(frame)
    daily = weather.daily
    lows = daily["temperature_2m_min"][:7]
    highs = daily["temperature_2m_max"][:7]
    wmin, wmax = min(lows), max(highs)
    rain_chances = daily.get("precipitation_probability_max", [0] * 7)[:7]
    bar_width = max(1, frame.geo.right_inner - 28)
    spaced = frame.geo.lines >= 30

    grid = Table.grid(padding=(0, 1))
    grid.add_column(width=2, no_wrap=True)
    grid.add_column(width=5, no_wrap=True)
    grid.add_column(width=6, justify="right", no_wrap=True)
    grid.add_column(width=4, justify="right", no_wrap=True)
    grid.add_column(no_wrap=True)
    grid.add_column(width=4, justify="right", no_wrap=True)

    for index in range(7):
        day = datetime.strptime(daily["time"][index], "%Y-%m-%d")
        name = "Today" if index == 0 else day.strftime("%a")
        bar = _range_bar(lows[index], highs[index], wmin, wmax, bar_width)
        _, kind = describe(daily["weather_code"][index])
        chance = round(rain_chances[index] or 0)
        grid.add_row(
            CONDITION_ICONS[kind],
            name,
            f"☂  {chance}%",
            f"{round(lows[index])}°",
            bar,
            f"{round(highs[index])}°",
        )
        if spaced and index < 6:
            grid.add_row("", "", "", "", "", "")
    return Padding(
        Group(Text("7-DAY FORECAST", style="bold"), Text(""), grid),
        (1, frame.padding),
    )
