"""Random greeting in a big block font (falls back to plain text if it won't fit)."""
from __future__ import annotations

import getpass
import random
from datetime import datetime
from typing import Callable

from rich.console import Group
from rich.padding import Padding
from rich.text import Text

from dashlib import BlockFont, Frame, Module, app_dir
from dashlib.blockfont import load_font_file
from dashlib.weather import describe, service

# Built-in 5-row block font (used when no custom font file is available).
BIG = {
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "B": ["████ ", "█   █", "████ ", "█   █", "████ "],
    "C": [" ████", "█    ", "█    ", "█    ", " ████"],
    "D": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "F": ["█████", "█    ", "████ ", "█    ", "█    "],
    "G": [" ████", "█    ", "█  ██", "█   █", " ████"],
    "H": ["█   █", "█   █", "█████", "█   █", "█   █"],
    "I": ["███", " █ ", " █ ", " █ ", "███"],
    "J": ["  ███", "   █ ", "   █ ", "█  █ ", " ██  "],
    "K": ["█   █", "█  █ ", "███  ", "█  █ ", "█   █"],
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "P": ["████ ", "█   █", "████ ", "█    ", "█    "],
    "Q": [" ███ ", "█   █", "█ █ █", "█  █ ", " ██ █"],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "S": [" ████", "█    ", " ███ ", "    █", "████ "],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "U": ["█   █", "█   █", "█   █", "█   █", " ███ "],
    "V": ["█   █", "█   █", "█   █", " █ █ ", "  █  "],
    "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    "X": ["█   █", " █ █ ", "  █  ", " █ █ ", "█   █"],
    "Y": ["█   █", " █ █ ", "  █  ", "  █  ", "  █  "],
    "Z": ["█████", "   █ ", "  █  ", " █   ", "█████"],
    ",": ["  ", "  ", "  ", " █", "█ "],
    ".": [" ", " ", " ", " ", "█"],
    "!": ["█", "█", "█", " ", "█"],
    "?": [" ███ ", "█   █", "  ██ ", "     ", "  █  "],
    "-": ["     ", "     ", "█████", "     ", "     "],
    " ": ["   "] * 5,
}


def day_period(hour: int) -> str:
    """Name of the time-of-day bucket used to choose greetings."""
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 16:
        return "afternoon"
    if 16 <= hour < 20:
        return "evening"
    return "night"


class Greeter:
    """Picks a random greeting and keeps it until it should change.

    A new message is chosen when the time of day changes, or when the current
    one no longer fits (for example after the terminal is resized).
    """

    def __init__(self) -> None:
        self.period: str | None = None
        self.text = ""

    def pick(self, now: datetime, options: list[str], period: str, fits: Callable[[str], bool]) -> str:
        fitting = [m for m in options if fits(m)]
        should_refresh = self.period != period or (fitting and self.text not in fitting)
        if should_refresh:
            self.period = period
            choices = fitting or options
            alternatives = [choice for choice in choices if choice != self.text]
            self.text = random.choice(alternatives or choices)
        return self.text


class Welcome(Module):
    name = "welcome"
    title = "Welcome banner"
    description = "Time-of-day greeting in a big font (greetings, font and name come from the config)."
    sizes = {"short": (2, 10), "normal": (3, 10), "tall": (4, 10), "half": (3, 6)}
    default_size = "normal"
    config_section = "appearance"
    defaults = {"show_welcome_summary": False, "font_file": "", "custom_font_gap": 0}

    def __init__(self, options=None, config=None) -> None:
        super().__init__(options, config)
        self.greeter = Greeter()
        self.font, self.note = self._load_font()

    def _load_font(self) -> tuple[BlockFont, str]:
        font_file = self.option("font_file") or None
        if not font_file:
            return BlockFont(BIG, 1), ""
        try:
            return load_font_file(font_file, app_dir(), int(self.option("custom_font_gap", 0))), ""
        except FileNotFoundError:
            return BlockFont(BIG, 1), f"font file '{font_file}' not found"
        except (OSError, ValueError, TypeError, AttributeError):
            return BlockFont(BIG, 1), "custom font could not be loaded"

    def _name(self) -> str:
        name = str(self.config.get("name") or "").strip()
        return name if name and name.upper() != "USER" else getpass.getuser().title()

    def render(self, frame: Frame):
        weather = service()
        weather.poll()
        inner_w = frame.width - 2 * frame.pad
        want_summary = bool(self.option("show_welcome_summary"))
        # rows left for the art after top/bottom padding and the optional summary
        art_rows = frame.height - (2 if frame.height >= 5 else 0) - (2 if want_summary else 0)

        def fits(text: str) -> bool:
            return (self.font.can_render(text) and self.font.width(text) <= inner_w
                    and self.font.rows(text) <= art_rows)

        greetings = (frame.config.get("greetings") or {})
        period = day_period(frame.now.hour)
        options = [m.format(name=self._name()) for m in greetings.get(period, ["Hello, {name}"])]
        text = self.greeter.pick(frame.now, options, period, fits)
        art = self.font.render(text) if fits(text) else text

        parts = [Text(art, style="bold", no_wrap=True, overflow="crop")]
        data = weather.latest
        if want_summary and data:
            cur = data.current
            label, _ = describe(cur["weather_code"])
            parts += [Text(""), Text(f"It's {round(cur['temperature_2m'])}° and {label.lower()} in {weather.location_name}.")]
        if self.note and frame.height >= art.count("\n") + 3:
            parts += [Text(""), Text(self.note, style="dim")]
        return Padding(Group(*parts), (1 if frame.height >= 5 else 0, frame.pad))
