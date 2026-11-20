import math
import random

from rich.padding import Padding
from rich.text import Text

from . import DashboardModule
from .context import Frame

MODULE = DashboardModule("aquarium", "Aquarium", row=5, column=5)

FISH_SPRITES = [
    (">", "<"),
    ("><>", "<><"),
    ("><(((o>", "<o)))><"),
    ("}><((((o>", "<o))))><{"),
]


class Aquarium:
    """Owns the animated fish-tank state and draws each tank frame."""

    def __init__(self, wave: str = " ") -> None:
        self.wave = wave
        self.w = self.h = 0
        self.frame = 0
        self.fish: list[dict] = []
        self.bubbles: list[list[float]] = []
        self.weeds: list[dict] = []
        self.sand_layers: list[str] = []
        self.sand_profile: list[int] = []
        self.bubbler_x = 0

    def _new_fish(self, initial: bool = False) -> dict:
        right, left = random.choice(FISH_SPRITES)
        direction = random.choice((1, -1))
        sprite = right if direction > 0 else left
        x = random.uniform(0, self.w) if initial else (
            -len(sprite) if direction > 0 else self.w
        )
        return {
            "x": x,
            "y": random.randint(1, self.h - 3),
            "d": direction,
            "speed": random.uniform(0.15, 0.6),
            "sprite": sprite,
        }

    def _fish_max_y(self, fish: dict) -> int:
        left = int(round(fish["x"]))
        covered = range(left, left + len(fish["sprite"]))
        sand_top = min(
            (self.sand_profile[x] for x in covered if 0 <= x < self.w),
            default=self.h - 2,
        )
        return min(self.h - 3, max(1, sand_top - 1))

    def _setup(self, width: int, height: int) -> None:
        self.w, self.h = width, height
        self.fish = [
            self._new_fish(initial=True)
            for _ in range(max(2, min(7, width // 14)))
        ]
        self.bubbles = []
        rng = random.Random()

        def smooth_noise(scale: int) -> list[float]:
            count = max(2, math.ceil(width / scale) + 2)
            knots = [rng.uniform(-1.0, 1.0) for _ in range(count)]
            values = []
            for x in range(width):
                position = x / scale
                left = math.floor(position)
                right = min(left + 1, len(knots) - 1)
                blend = position - left
                blend = (1.0 - math.cos(math.pi * blend)) / 2.0
                values.append(knots[left] * (1.0 - blend) + knots[right] * blend)
            return values

        broad = smooth_noise(max(12, width // 5))
        medium = smooth_noise(max(5, width // 12))
        self.sand_layers = ["░" * width for _ in range(3)]
        max_dune = 3 if height >= 12 else 2 if height >= 8 else 1
        base_surface = height - 2
        self.sand_profile = [
            max(
                height - 2 - max_dune,
                base_surface
                - round(
                    (
                        (broad[x] * 0.75 + medium[x] * 0.25 + 1.0)
                        / 2.0
                    )
                    * max_dune
                ),
            )
            for x in range(width)
        ]
        self.weeds = []
        for _ in range(max(3, width // 12)):
            base_x = rng.randint(1, max(1, width - 2))
            for stem in range(rng.randint(1, 3)):
                offset = stem - 1 if rng.randint(0, 1) else stem
                self.weeds.append({
                    "x": max(1, min(width - 2, base_x + offset)),
                    "height": rng.randint(2, max(2, min(7, height - 3))),
                    "phase": rng.uniform(0.0, math.tau),
                    "sway": rng.uniform(0.35, 1.15),
                    "fork": rng.random() > 0.58,
                })
        self.bubbler_x = rng.randint(2, width - 3)

    def _step(self) -> None:
        self.frame += 1
        for index, fish in enumerate(self.fish):
            fish["x"] += fish["d"] * fish["speed"]
            if fish["x"] > self.w or fish["x"] < -len(fish["sprite"]):
                self.fish[index] = self._new_fish()
                continue
            if random.random() < 0.01:
                fish["y"] += random.choice((-1, 1))
            fish["y"] = min(max(1, fish["y"]), self._fish_max_y(fish))
            if random.random() < 0.015:
                head = fish["x"] + (
                    len(fish["sprite"]) if fish["d"] > 0 else -1
                )
                self.bubbles.append([head, fish["y"] - 1.0])
        if random.random() < 0.08:
            bubble_y = (
                self.sand_profile[self.bubbler_x] - 1.0
                if self.sand_profile
                else self.h - 2.0
            )
            self.bubbles.append([float(self.bubbler_x), bubble_y])
        for bubble in self.bubbles:
            bubble[1] -= 0.25
            bubble[0] += random.uniform(-0.3, 0.3)
        self.bubbles = [bubble for bubble in self.bubbles if bubble[1] >= 1]

    def frame_text(self, width: int, height: int) -> Text:
        if width < 20 or height < 5:
            return Text("")
        if (width, height) != (self.w, self.h):
            self._setup(width, height)
        self._step()
        grid = [[" "] * width for _ in range(height)]
        bold = [[False] * width for _ in range(height)]
        if self.wave:
            shift = self.frame // 2
            for x in range(width):
                grid[0][x] = self.wave[(x - shift) % len(self.wave)]
        deep, middle, surface = self.sand_layers
        for x, top in enumerate(self.sand_profile):
            for y in range(top, height):
                depth = y - top
                grid[y][x] = surface[x] if depth == 0 else (
                    middle[x] if depth == 1 else deep[x]
                )
        for weed in self.weeds:
            base_x = weed["x"]
            for k in range(weed["height"]):
                sand_top = (
                    self.sand_profile[base_x]
                    if base_x < len(self.sand_profile)
                    else height - 2
                )
                y = sand_top - 1 - k
                if y < 2:
                    break
                ratio = k / max(1, weed["height"] - 1)
                phase = weed["phase"] + k * 0.72 + self.frame * 0.10
                x = base_x + int(round(math.sin(phase) * weed["sway"] * ratio))
                if not 0 <= x < width:
                    continue
                wind = math.sin(phase)
                if k == weed["height"] - 1:
                    char = "∧"
                elif weed["fork"] and k in (2, 4) and k < weed["height"] - 1:
                    char = "/" if wind > 0 else "\\"
                elif wind > 0.35:
                    char = ")"
                elif wind < -0.35:
                    char = "("
                else:
                    char = "│"
                grid[y][x] = char
                bold[y][x] = True
        for bubble_x, bubble_y in self.bubbles:
            x, y = int(round(bubble_x)), int(round(bubble_y))
            if 0 <= x < width and 1 <= y < height - 1:
                depth = y / height
                grid[y][x] = "o" if depth < 0.25 else "°" if depth < 0.50 else "."
        for fish in self.fish:
            x0, y = int(round(fish["x"])), fish["y"]
            for offset, char in enumerate(fish["sprite"]):
                if 0 <= x0 + offset < width:
                    grid[y][x0 + offset] = char
                    bold[y][x0 + offset] = True
        text = Text(no_wrap=True, overflow="crop", end="")
        for y in range(height):
            x = 0
            while x < width:
                is_bold = bold[y][x]
                end = x
                while end < width and bold[y][end] == is_bold:
                    end += 1
                text.append("".join(grid[y][x:end]), style="bold" if is_bold else None)
                x = end
            if y < height - 1:
                text.append("\n")
        return text

    def render(self, frame: Frame, welcome_height: int):
        width = frame.geo.left_inner
        height = frame.geo.body_h - welcome_height
        return Padding(
            self.frame_text(width, height),
            (0, 0, 0, frame.padding),
        )
