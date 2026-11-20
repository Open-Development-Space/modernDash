"""BlockFont: multi-row glyph fonts rendered as ASCII art, plus font-file loading."""
from __future__ import annotations

import json
import os


class BlockFont:
    """A font of multi-row glyphs that renders strings as ASCII art.

    ``glyphs`` maps a character to a list of equal-count text rows. Glyphs are
    trimmed of trailing blanks (FIGlet-style JSON fonts pad every glyph) and
    padded to a common height. Lookup falls back to the upper/lower-case
    variant of a character, so an upper-case-only font still renders
    mixed-case text.
    """

    def __init__(self, glyphs: dict, gap: int = 1) -> None:
        height = max(len(rows) for rows in glyphs.values())
        space_w = max(3, height // 2)  # width used for blank glyphs
        self.glyphs: dict[str, list[str]] = {}
        for ch, rows in glyphs.items():
            rows = list(rows) + [""] * (height - len(rows))
            width = max(len(r.rstrip()) for r in rows) or space_w
            self.glyphs[ch] = [r[:width].ljust(width) for r in rows]
        self.glyphs.setdefault(" ", [" " * space_w] * height)
        self.height = height
        self.gap = gap
        self._cache: dict[str, str] = {}

    def _glyph(self, ch: str) -> list[str] | None:
        for candidate in (ch, ch.upper(), ch.lower()):
            if candidate in self.glyphs:
                return self.glyphs[candidate]
        return None

    def can_render(self, text: str) -> bool:
        """True if every character of ``text`` has a glyph."""
        return all(self._glyph(c) is not None for c in text)

    def render(self, text: str) -> str:
        """Return ``text`` as multi-line art, without empty rows above/below."""
        if text in self._cache:
            return self._cache[text]
        blank = [" " * 3] * self.height
        glyphs = [self._glyph(c) or blank for c in text]
        sep = " " * self.gap
        rows = [sep.join(g[r] for g in glyphs) for r in range(self.height)]
        while rows and not rows[0].strip():
            rows.pop(0)
        while rows and not rows[-1].strip():
            rows.pop()
        out = "\n".join(rows)
        self._cache[text] = out
        return out

    def width(self, text: str) -> int:
        """Width in columns of ``text`` once rendered."""
        return max((len(r) for r in self.render(text).split("\n")), default=0)

    def rows(self, text: str) -> int:
        """Number of rows ``text`` takes once rendered."""
        return self.render(text).count("\n") + 1


def find_font_file(font_file: str, base_dir: str) -> str | None:
    """Locate a font JSON by name, relative path or absolute path."""
    candidates = (
        os.path.join(base_dir, font_file),
        os.path.join(base_dir, "dbfonts", os.path.basename(font_file)),
        font_file,
    )
    return next((p for p in candidates if os.path.isfile(p)), None)


def load_font_file(font_file: str, base_dir: str, gap: int = 0) -> BlockFont:
    """Load a JSON font. Raises FileNotFoundError / ValueError when unusable."""
    path = find_font_file(font_file, base_dir)
    if path is None:
        raise FileNotFoundError(font_file)
    with open(path, encoding="utf-8") as f:
        return BlockFont(json.load(f), gap)
