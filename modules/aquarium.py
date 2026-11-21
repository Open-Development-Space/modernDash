"""An animated ASCII fish tank that fills whatever space it is given."""
from __future__ import annotations

import math
import random

from rich.padding import Padding
from rich.text import Text

from dashlib import Frame, Module

# Fish: (sprite facing right, sprite facing left).
FISH_SPRITES = [
    (">", "<"),
    ("><>", "<><"),
    ("><(((o>", "<o)))><"),
    ("}><((((o>", "<o))))><{"),
]


class Aquarium(Module):
    """Surface waves, fish that swim across and re-enter on the far side,
    bubbles (from the fish and a bubbler on the sand), swaying seaweed and
    sand. If the size changes, the tank is rebuilt to fit."""

    name = "aquarium"
    title = "Aquarium"
    description = "Animated fish tank (option: wave, the surface character)."
    sizes = {"small": (3, 5), "medium": (5, 7), "large": (7, 10), "tall": (8, 10), "wide": (4, 14), "full": (10, 14)}
    default_size = "large"
    config_section = "aquarium"
    defaults = {"wave": " "}

    def __init__(self, options=None, config=None) -> None:
        super().__init__(options, config)
        self.w = self.h = 0
        self.frame = 0
        self.fish: list[dict] = []
        self.bubbles: list[list[float]] = []   # [x, y]
        self.weeds: list[dict] = []
        self.sand_layers: list[str] = []
        self.sand_profile: list[int] = []
        self.bubbler_x = 0

    def render(self, frame: Frame):
        pad = frame.pad
        width = max(0, frame.width - 2 * pad)
        return Padding(self.frame_text(width, frame.height, str(self.option("wave"))), (0, 0, 0, pad))

    def _new_fish(self, initial: bool = False) -> dict:
        """Create a fish. Respawned fish enter from the edge they swim away from."""
        right, left = random.choice(FISH_SPRITES)
        direction = random.choice((1, -1))
        sprite = right if direction > 0 else left
        if initial:
            x = random.uniform(0, self.w)
        else:
            x = -len(sprite) if direction > 0 else self.w
        return {
            "x": x,
            "y": random.randint(1, max(1, self.h - 3)),
            "d": direction,
            "speed": random.uniform(0.15, 0.6),  # columns per frame
            "sprite": sprite,
        }

    def _fish_max_y(self, fish: dict) -> int:
        """Return the lowest safe row for a fish above the sand under its body."""
        left = int(round(fish["x"]))
        covered = range(left, left + len(fish["sprite"]))
        sand_top = min(
            (self.sand_profile[x] for x in covered if 0 <= x < self.w),
            default=self.h - 2,
        )
        return min(self.h - 3, max(1, sand_top - 1))

    def _setup(self, w: int, h: int) -> None:
        """(Re)build the tank for a new size."""
        self.w, self.h = w, h
        self.fish = [self._new_fish(initial=True) for _ in range(max(2, min(7, w // 14)))]
        self.bubbles = []
        rng = random.Random()

        def smooth_noise(scale: int) -> list[float]:
            count = max(2, math.ceil(w / scale) + 2)
            knots = [rng.uniform(-1.0, 1.0) for _ in range(count)]
            values = []
            for x in range(w):
                position = x / scale
                left = math.floor(position)
                right = min(left + 1, len(knots) - 1)
                t = position - left
                t = (1.0 - math.cos(math.pi * t)) / 2.0
                values.append(knots[left] * (1.0 - t) + knots[right] * t)
            return values

        broad = smooth_noise(max(12, w // 5))
        medium = smooth_noise(max(5, w // 12))
        self.sand_layers = ["░" * w for _ in range(3)]

        max_dune = 3 if h >= 12 else 2 if h >= 8 else 1
        base_surface = h - 2
        self.sand_profile = [
            max(
                h - 2 - max_dune,
                base_surface - round(((broad[x] * 0.75 + medium[x] * 0.25 + 1.0) / 2.0) * max_dune),
            )
            for x in range(w)
        ]

        self.weeds = []
        for _ in range(max(3, w // 12)):
            base_x = rng.randint(1, max(1, w - 2))
            for stem in range(rng.randint(1, 3)):
                offset = stem - 1 if rng.randint(0, 1) else stem
                self.weeds.append({
                    "x": max(1, min(w - 2, base_x + offset)),
                    "height": rng.randint(2, max(2, min(7, h - 3))),
                    "phase": rng.uniform(0.0, math.tau),
                    "sway": rng.uniform(0.35, 1.15),
                    "fork": rng.random() > 0.58,
                })
        self.bubbler_x = rng.randint(2, w - 3)

    def _step(self) -> None:
        """Advance the simulation by one frame."""
        self.frame += 1
        for i, fish in enumerate(self.fish):
            fish["x"] += fish["d"] * fish["speed"]
            if fish["x"] > self.w or fish["x"] < -len(fish["sprite"]):
                self.fish[i] = self._new_fish()
                continue
            if random.random() < 0.01:  # occasional drift up or down
                fish["y"] += random.choice((-1, 1))
            fish["y"] = min(max(1, fish["y"]), self._fish_max_y(fish))
            if random.random() < 0.015:  # blow a bubble from the head
                head = fish["x"] + (len(fish["sprite"]) if fish["d"] > 0 else -1)
                self.bubbles.append([head, fish["y"] - 1.0])
        if random.random() < 0.08:  # the bubbler on the sand
            bubble_y = self.sand_profile[self.bubbler_x] - 1.0 if self.sand_profile else self.h - 2.0
            self.bubbles.append([float(self.bubbler_x), bubble_y])
        for bubble in self.bubbles:
            bubble[1] -= 0.25                       # rise
            bubble[0] += random.uniform(-0.3, 0.3)  # wobble
        self.bubbles = [b for b in self.bubbles if b[1] >= 1]

    def frame_text(self, w: int, h: int, wave: str = " ") -> Text:
        """Advance one frame and draw the tank at ``w`` x ``h`` characters."""
        if w < 20 or h < 5:
            return Text("")
        if (w, h) != (self.w, self.h):
            self._setup(w, h)
        self._step()

        grid = [[" "] * w for _ in range(h)]
        bold = [[False] * w for _ in range(h)]

        if wave:  # water surface
            shift = self.frame // 2
            for x in range(w):
                grid[0][x] = wave[(x - shift) % len(wave)]

        # Sand: three tones per column (deep grains, packed mid-layer, surface).
        deep, middle, surface = self.sand_layers
        for x, top in enumerate(self.sand_profile):
            for y in range(top, h):
                depth = y - top
                grid[y][x] = surface[x] if depth == 0 else middle[x] if depth == 1 else deep[x]

        # Seaweed bends continuously and branches near the tips.
        for weed in self.weeds:
            base_x, height = weed["x"], weed["height"]
            phase, sway = weed["phase"], weed["sway"]
            for k in range(height):
                sand_top = self.sand_profile[base_x] if base_x < len(self.sand_profile) else h - 2
                y = sand_top - 1 - k
                if y < 2:
                    break
                height_ratio = k / max(1, height - 1)
                wind = math.sin(phase + k * 0.72 + self.frame * 0.10)
                x = base_x + int(round(wind * sway * height_ratio))
                if not 0 <= x < w:
                    continue
                if k == height - 1:
                    ch = "∧"
                elif weed["fork"] and k in (2, 4) and k < height - 1:
                    ch = "/" if wind > 0 else "\\"
                elif wind > 0.35:
                    ch = ")"
                elif wind < -0.35:
                    ch = "("
                else:
                    ch = "│"
                grid[y][x] = ch
                bold[y][x] = True

        for bx, by in self.bubbles:  # bubbles grow as they rise
            x, y = int(round(bx)), int(round(by))
            if 0 <= x < w and 1 <= y < h - 1:
                depth = y / h
                grid[y][x] = "o" if depth < 0.25 else "°" if depth < 0.50 else "."

        for fish in self.fish:  # fish on top, in bold
            x0, y = int(round(fish["x"])), fish["y"]
            for j, ch in enumerate(fish["sprite"]):
                if 0 <= x0 + j < w and 0 <= y < h:
                    grid[y][x0 + j] = ch
                    bold[y][x0 + j] = True

        # grid -> Text, grouping runs of the same style to keep it cheap
        text = Text(no_wrap=True, overflow="crop", end="")
        for y in range(h):
            x = 0
            while x < w:
                is_bold = bold[y][x]
                x2 = x
                while x2 < w and bold[y][x2] == is_bold:
                    x2 += 1
                text.append("".join(grid[y][x:x2]), style="bold" if is_bold else None)
                x = x2
            if y < h - 1:
                text.append("\n")
        return text
