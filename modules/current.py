from datetime import datetime

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from . import DashboardModule
from .context import Frame
from .weather_display import ART, BAR_LEVELS, describe

MODULE = DashboardModule("current", "Current conditions", row=2, column=2)

_TEMP_GLYPHS = {
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


def _temperature_art(value: str) -> str:
    rows_by_char = []
    for char in value:
        rows = _TEMP_GLYPHS[char]
        width = max((len(row.rstrip()) for row in rows), default=0)
        rows_by_char.append([row[:width].ljust(width) for row in rows])
    rendered = [
        " ".join(glyph[row] for glyph in rows_by_char)
        for row in range(3)
    ]
    while rendered and not rendered[0].strip():
        rendered.pop(0)
    while rendered and not rendered[-1].strip():
        rendered.pop()
    return "\n".join(rendered)


def _clock(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M").strftime("%I:%M %p").lstrip("0")


def _rain_panel(weather, width: int, rain_full: float) -> list[RenderableType]:
    hours = weather.rain
    if not hours or width < 12:
        return []
    count = min(len(hours), width)
    bars: list[str] = []
    axis = [" "] * width
    for index in range(0, count, 6):
        when = hours[index].time
        label = "Now" if index == 0 else f"{when.hour % 12 or 12}{'a' if when.hour < 12 else 'p'}"
        position = index * width // count
        if position + len(label) <= len(axis):
            axis[position:position + len(label)] = list(label)
    for index, hour in enumerate(hours[:count]):
        start = index * width // count
        end = (index + 1) * width // count
        cell_width = end - start
        bar = (
            "·"
            if hour.amount == 0
            else BAR_LEVELS[min(7, int(hour.amount / rain_full * 7))]
        )
        bars.append(bar * cell_width)
    title = weather.rain_outlook()
    total = sum(hour.amount for hour in hours)
    if total >= 0.01:
        title += f" · {total:.2f} in"
    return [
        Text(title, style="bold", no_wrap=True, overflow="ellipsis"),
        Text("".join(bars), no_wrap=True),
        Text("".join(axis), no_wrap=True),
    ]


def render(frame: Frame):
    weather = frame.weather
    if weather is None:
        return Padding(Text(frame.status), (1, frame.padding))
    current, daily = weather.current, weather.daily
    label, kind = describe(current["weather_code"])
    if kind == "clear" and not current.get("is_day", 1):
        kind = "night"
    art = Text("\n".join(ART[kind]))
    temperature = Text(
        _temperature_art(f"{round(current['temperature_2m'])}°"),
        style="bold",
    )
    stats = [
        ("Feels", f"{round(current['apparent_temperature'])}°"),
        ("Humidity", f"{current['relative_humidity_2m']}%"),
        ("Wind", f"{round(current['wind_speed_10m'])} mph"),
        ("Rain", f"{daily['precipitation_probability_max'][0]}%"),
        ("Hi/Lo", f"{round(daily['temperature_2m_max'][0])}°/{round(daily['temperature_2m_min'][0])}°"),
        ("UV", f"{round(daily['uv_index_max'][0] or 0)}"),
        ("Sunrise", _clock(daily["sunrise"][0])),
        ("Sunset", _clock(daily["sunset"][0])),
    ]
    stats = stats[:max(4, min(len(stats), frame.geo.day_h - 6))]
    extras = Table.grid(padding=(0, 1))
    extras.add_column()
    extras.add_column(justify="right")
    for name, value in stats:
        extras.add_row(name, value)

    wide = frame.geo.right_inner >= 44
    main = Table.grid(padding=(0, 3), expand=True)
    if wide:
        main.add_column()
        main.add_column(vertical="middle")
        main.add_column(vertical="middle")
        main.add_row(art, temperature, extras)
    else:
        main.add_column()
        main.add_column(vertical="middle")
        main.add_row(Group(art, temperature), extras)

    block_height = max(5, len(stats)) if wide else max(8, len(stats))
    spare = frame.geo.day_h - (block_height + 4)
    parts: list[RenderableType] = [Text(f"NOW  ·  {label}", style="bold")]
    if spare >= 1:
        parts.append(Text(""))
    parts.append(main)
    rain = _rain_panel(weather, frame.geo.right_inner, frame.rain_full)
    if rain:
        if spare >= 2:
            parts.append(Text(""))
        parts.extend(rain)
    return Padding(Group(*parts), (0, frame.padding))
