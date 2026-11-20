"""Current conditions: ASCII icon, big temperature, stats and an hourly rain chart."""
from __future__ import annotations

from datetime import datetime

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from dashlib import BlockFont, Frame, Module
from dashlib.weather import ISO_MINUTE, Weather, describe, service

# 3-row font for the big temperature readout.
SMALL = {
    "0": ["┏━┓", "┃ ┃", "┗━┛"],
    "1": ["╺┓ ", " ┃ ", "╺┻╸"],
    "2": ["┏━┓", "┏━┛", "┗━╸"],
    "3": ["┏━┓", "╺━┫", "┗━┛"],
    "4": ["╻ ╻", "┗━┫", "  ╹"],
    "5": ["┏━╸", "┗━┓", "┗━┛"],
    "6": ["┏━┓", "┣━┓", "┗━┛"],
    "7": ["┏━┓", "  ┃", "  ╹"],
    "8": ["┏━┓", "┣━┫", "┗━┛"],
    "9": ["┏━┓", "┗━┫", "┗━┛"],
    "-": ["   ", "╺━╸", "   "],
    "°": ["┏┓ ", "┗┛ ", "   "],
}
TEMP_FONT = BlockFont(SMALL, gap=1)

# 5-line, 13-column ASCII icons for the current condition.
ART = {
    "clear": [
        r"             ",
        r"    \___/    ",
        r"  __/   \__  ",
        r"    \___/    ",
        r"    /   \    ",
    ],
    "night": [
        r"             ",
        r"    ,-,-.    ",
        r"   /.( +.\   ",
        r"   \ {. */   ",
        r"    `-`-'    ",
    ],
    "partly": [
        r"   \___/     ",
        r' __/ .--.    ',
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"             ",
    ],
    "cloud": [
        r"             ",
        r"     .--.    ",
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"             ",
    ],
    "rain": [
        r"     .--.    ",
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"    ' ' ' '  ",
        r"   ' ' ' '   ",
    ],
    "snow": [
        r"     .--.    ",
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"   *  *  *   ",
        r"  *  *  *    ",
    ],
    "storm": [
        r"     .--.    ",
        r"  .-(    ).  ",
        r" (___.__)__) ",
        r"    /_  /_   ",
        r"     /   /   ",
    ],
    "fog": [
        r"             ",
        r" _ - _ - _ - ",
        r"  _ - _ - _  ",
        r" _ - _ - _ - ",
        r"             ",
    ],
}

BAR_LEVELS = "▁▂▃▄▅▆▇█"  # eight bar heights, lowest to highest


def clock(iso: str) -> str:
    """``'2026-11-18T16:42'`` -> ``'4:42 PM'``."""
    return datetime.strptime(iso, ISO_MINUTE).strftime("%I:%M %p").lstrip("0")


def rain_panel(weather: Weather, width: int, rain_full: float) -> list[RenderableType]:
    """Outlook line plus an hourly bar chart for the next 24 hours.

    Each character is one hour (two when there is room). A dot means no rain;
    ``▁`` to ``█`` grow with the expected amount, scaled so that ``rain_full``
    inches per hour is a full bar. A time axis labels every sixth hour.
    """
    hours = weather.rain
    if not hours or width < 12:
        return []

    n = min(len(hours), width)
    bars: list[str] = []
    axis = [" "] * width
    for k in range(0, n, 6):
        when = hours[k].time
        label = "Now" if k == 0 else f"{when.hour % 12 or 12}{'a' if when.hour < 12 else 'p'}"
        pos = k * width // n
        if pos + len(label) <= len(axis):
            axis[pos:pos + len(label)] = list(label)

    for i, hour in enumerate(hours[:n]):
        cell_width = (i + 1) * width // n - i * width // n
        bar = "·" if hour.amount == 0 else BAR_LEVELS[min(7, int(hour.amount / rain_full * 7))]
        bars.append(bar * cell_width)

    title = weather.rain_outlook()
    total = sum(h.amount for h in hours)
    if total >= 0.01:
        title += f" · {total:.2f} in"

    return [
        Text(title, style="bold", no_wrap=True, overflow="ellipsis"),
        Text("".join(bars), no_wrap=True),
        Text("".join(axis), no_wrap=True),
    ]


class Day(Module):
    name = "day"
    title = "Current conditions"
    description = "Now: icon, temperature, stats and the next 24 hours of rain."
    sizes = {"compact": (3, 4), "normal": (4, 4), "tall": (5, 4), "wide": (4, 6)}
    default_size = "normal"
    config_section = "weather"
    defaults = {"rain_full": 0.25}

    def render(self, frame: Frame):
        weather = service()
        weather.poll()
        w = weather.latest
        if w is None:
            return Padding(Text(weather.status), (1, frame.pad))
        cur, daily = w.current, w.daily
        label, kind = describe(cur["weather_code"])
        if kind == "clear" and not cur.get("is_day", 1):
            kind = "night"

        art = Text("\n".join(ART[kind]))
        temp = Text(TEMP_FONT.render(f"{round(cur['temperature_2m'])}°"), style="bold")

        # Stats in priority order; as many are shown as the panel height allows.
        stats = [
            ("Feels", f"{round(cur['apparent_temperature'])}°"),
            ("Humidity", f"{cur['relative_humidity_2m']}%"),
            ("Wind", f"{round(cur['wind_speed_10m'])} mph"),
            ("Rain", f"{daily['precipitation_probability_max'][0]}%"),
            ("Hi/Lo", f"{round(daily['temperature_2m_max'][0])}°/{round(daily['temperature_2m_min'][0])}°"),
            ("UV", f"{round(daily['uv_index_max'][0] or 0)}"),
            ("Sunrise", clock(daily["sunrise"][0])),
            ("Sunset", clock(daily["sunset"][0])),
        ]
        avail = frame.height
        inner = frame.width - 2 * frame.pad
        stats = stats[:max(4, min(len(stats), avail - 6))]  # 6 = header, rain rows, spacers

        extras = Table.grid(padding=(0, 1))
        extras.add_column()
        extras.add_column(justify="right")
        for name, value in stats:
            extras.add_row(name, value)

        wide = inner >= 44
        main = Table.grid(padding=(0, 3), expand=True)
        if wide:  # art | temperature | stats
            main.add_column()
            main.add_column(vertical="middle")
            main.add_column(vertical="middle")
            main.add_row(art, temp, extras)
        else:     # art over temperature, stats to the right
            main.add_column()
            main.add_column(vertical="middle")
            main.add_row(Group(art, temp), extras)

        # Blank spacer lines are only kept when the panel has room for them.
        block_h = max(5, len(stats)) if wide else max(8, len(stats))
        spare = avail - (block_h + 4)  # 4 = header + rain title + bars + axis

        parts: list[RenderableType] = [Text(f"NOW  ·  {label}", style="bold")]
        if spare >= 1:
            parts.append(Text(""))
        parts.append(main)

        rain = rain_panel(w, inner, float(self.option("rain_full")))
        if rain:
            if spare >= 2:
                parts.append(Text(""))
            parts += rain

        return Padding(Group(*parts), (0, frame.pad))
