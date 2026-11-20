"""Copy this file to modules/<yourname>.py to make a new module.

Files starting with an underscore are ignored by the dashboard, so this one is
only an example. A new module shows up in `modernDash modules` and in the
layout editor automatically; nothing else needs to be edited.
"""
from __future__ import annotations

from rich.padding import Padding
from rich.text import Text

from dashlib import Frame, Module


class Hello(Module):
    name = "hello"                      # id used in the layout config
    title = "Hello"                     # label in the layout editor
    description = "Says hello (option: text)."
    # Size variations in grid cells, as {label: (rows, cols)}.
    sizes = {"small": (1, 3), "big": (2, 6)}
    default_size = "small"
    defaults = {"text": "Hello!"}       # override per placement via "options" in the layout

    def render(self, frame: Frame):
        # frame.width / frame.height are the characters available to this module;
        # frame.rows / frame.cols are its size in grid cells.
        text = Text(str(self.option("text")), style="bold" if frame.rows > 1 else "")
        return Padding(text, (0, frame.pad))
