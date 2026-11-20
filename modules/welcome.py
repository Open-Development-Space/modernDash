import json
import os
import random
from datetime import datetime
from typing import Callable

from rich.console import Group
from rich.padding import Padding
from rich.text import Text

from . import DashboardModule
from .context import Frame
from .weather_display import describe

MODULE = DashboardModule("welcome", "Welcome banner", row=2, column=5)

_DEFAULT_GLYPHS = {
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


class BlockFont:
    def __init__(self, glyphs: dict, gap: int = 1) -> None:
        height = max(len(rows) for rows in glyphs.values())
        space_width = max(3, height // 2)
        self.glyphs: dict[str, list[str]] = {}
        for char, rows in glyphs.items():
            rows = list(rows) + [""] * (height - len(rows))
            width = max(len(row.rstrip()) for row in rows) or space_width
            self.glyphs[char] = [row[:width].ljust(width) for row in rows]
        self.glyphs.setdefault(" ", [" " * space_width] * height)
        self.height = height
        self.gap = gap
        self.cache: dict[str, str] = {}

    def _glyph(self, char: str) -> list[str] | None:
        for candidate in (char, char.upper(), char.lower()):
            if candidate in self.glyphs:
                return self.glyphs[candidate]
        return None

    def can_render(self, text: str) -> bool:
        return all(self._glyph(char) is not None for char in text)

    def render(self, text: str) -> str:
        if text in self.cache:
            return self.cache[text]
        blank = [" " * 3] * self.height
        glyphs = [self._glyph(char) or blank for char in text]
        separator = " " * self.gap
        rows = [
            separator.join(glyph[row] for glyph in glyphs)
            for row in range(self.height)
        ]
        while rows and not rows[0].strip():
            rows.pop(0)
        while rows and not rows[-1].strip():
            rows.pop()
        result = "\n".join(rows)
        self.cache[text] = result
        return result

    def width(self, text: str) -> int:
        return max((len(row) for row in self.render(text).split("\n")), default=0)


def _period(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 16:
        return "afternoon"
    if 16 <= hour < 20:
        return "evening"
    return "night"


class Welcome:
    """Owns greeting selection, font loading, and welcome-banner rendering."""

    def __init__(
        self,
        font_file: str | None,
        font_gap: int,
        greetings: dict,
        user_name: str,
        show_summary: bool,
    ) -> None:
        self.font, self.font_note = self._load_font(font_file, font_gap)
        self.greetings = greetings
        self.user_name = user_name
        self.show_summary = show_summary
        self.period: str | None = None
        self.text = ""

    @staticmethod
    def _load_font(font_file: str | None, gap: int) -> tuple[BlockFont, str]:
        try:
            if font_file:
                here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                path = next(
                    (
                        candidate
                        for candidate in (
                            os.path.join(here, font_file),
                            os.path.join(here, "dbfonts", os.path.basename(font_file)),
                            font_file,
                        )
                        if os.path.isfile(candidate)
                    ),
                    None,
                )
                if path is None:
                    return BlockFont(_DEFAULT_GLYPHS, 1), f"font file '{font_file}' not found"
                with open(path, encoding="utf-8") as file:
                    return BlockFont(json.load(file), gap), ""
        except (OSError, ValueError, TypeError, AttributeError):
            return BlockFont(_DEFAULT_GLYPHS, 1), "custom font could not be loaded"
        return BlockFont(_DEFAULT_GLYPHS, 1), ""

    def _greeting(self, now: datetime, fits: Callable[[str], bool]) -> str:
        period = _period(now.hour)
        options = [message.format(name=self.user_name) for message in self.greetings[period]]
        fitting = [message for message in options if fits(message)]
        if self.period != period or (fitting and self.text not in fitting):
            self.period = period
            choices = fitting or options
            alternatives = [choice for choice in choices if choice != self.text]
            self.text = random.choice(alternatives or choices)
        return self.text

    def render(self, frame: Frame):
        available = frame.geo.left_inner

        def fits(text: str) -> bool:
            return self.font.can_render(text) and self.font.width(text) <= available

        message = self._greeting(frame.now, fits)
        art = self.font.render(message) if fits(message) else message
        summary = ""
        if self.show_summary and frame.weather:
            current = frame.weather.current
            label, _ = describe(current["weather_code"])
            summary = (
                f"It's {round(current['temperature_2m'])}° and "
                f"{label.lower()} in {frame.location}."
            )
        height = art.count("\n") + 5
        rendered = Padding(
            Group(Text(art, style="bold"), Text(""), Text(summary)),
            (1, frame.padding),
        )
        return rendered, height
