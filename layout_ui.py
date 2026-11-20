"""The layout editor: drag modules around a grid with the mouse.

    drag a module        move it (snaps to the grid, refuses overlaps)
    drag its ◢ corner    resize it to the nearest size the module supports
    right-click          cycle through the module's sizes
    sidebar buttons      add / remove modules, pick a size, grow or shrink the grid
    ctrl+s               save to the config file (a running dashboard picks it up)
"""
from __future__ import annotations

import copy

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Static

from dashlib.config import DEFAULT_LAYOUT, load_config, save_layout
from dashlib.layout_state import EditorState
from dashlib.registry import discover

PALETTE = ["#2b4c7e", "#3b6b4f", "#7a4a2a", "#5a3d7a", "#2f6f73", "#7a3a4f", "#6b6b2a", "#3c3c8a"]


def button(label: str, id: str | None = None, variant: str = "default") -> Button:
    try:
        return Button(label, id=id, variant=variant, compact=True)
    except TypeError:  # older Textual without compact buttons
        return Button(label, id=id, variant=variant)


class SizeButton(Button):
    """A button that remembers which size it stands for."""

    def __init__(self, label: str, rows: int, cols: int, current: bool) -> None:
        super().__init__(label, variant="primary" if current else "default")
        self.size_rows, self.size_cols = rows, cols


class Canvas(Widget, can_focus=True):
    """The grid preview. Each grid cell is drawn ``cw x ch`` characters large."""

    DEFAULT_CSS = "Canvas { width: 1fr; height: 1fr; padding: 0; border: none; }"

    class Changed(Message):
        """Selection or layout changed; the sidebar should refresh."""

    def __init__(self, state: EditorState) -> None:
        super().__init__()
        self.state = state
        self.drag: dict | None = None
        self.ghost: tuple[int, int, int, int, bool] | None = None

    # -- geometry -----------------------------------------------------------
    def cell(self) -> tuple[int, int]:
        width, height = self.size.width, self.size.height
        return max(2, width // self.state.cols), max(1, height // self.state.rows)

    def grid_pos(self, x: int, y: int) -> tuple[int, int]:
        """Grid (row, col) under a pixel position; may be outside the grid."""
        cw, ch = self.cell()
        return y // ch, x // cw

    # -- mouse --------------------------------------------------------------
    def on_mouse_down(self, event: events.MouseDown) -> None:
        s = self.state
        cw, ch = self.cell()
        row, col = self.grid_pos(event.x, event.y)
        p = s.at(row, col) if 0 <= row < s.rows and 0 <= col < s.cols else None
        s.selected = p.id if p else None
        if p and event.button == 3:
            s.cycle_size(p.id)
        elif p and event.button == 1:
            x1, y1 = (p.col + p.cols) * cw, (p.row + p.rows) * ch
            resizing = event.y == y1 - 1 and x1 - 2 <= event.x < x1
            self.drag = {"mode": "resize" if resizing else "move", "pid": p.id,
                         "off_r": row - p.row, "off_c": col - p.col}
            self.capture_mouse()
        self.post_message(self.Changed())
        self.refresh()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self.drag:
            return
        s = self.state
        p = s.get(self.drag["pid"])
        if p is None:
            return
        row, col = self.grid_pos(event.x, event.y)
        if self.drag["mode"] == "move":
            new_row = max(0, min(s.rows - p.rows, row - self.drag["off_r"]))
            new_col = max(0, min(s.cols - p.cols, col - self.drag["off_c"]))
            self.ghost = (new_row, new_col, p.rows, p.cols, s.fits(new_row, new_col, p.rows, p.cols, ignore=p.id))
        else:
            size = s.nearest_size(p.id, row - p.row + 1, col - p.col + 1)
            self.ghost = (p.row, p.col, size[0], size[1], True) if size else None
        self.refresh()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self.drag:
            return
        s, ghost, drag = self.state, self.ghost, self.drag
        self.drag = self.ghost = None
        self.release_mouse()
        if ghost:
            row, col, rows, cols, valid = ghost
            if valid and drag["mode"] == "move":
                s.move(drag["pid"], row, col)
            elif valid:
                s.resize(drag["pid"], rows, cols)
        self.post_message(self.Changed())
        self.refresh()

    # -- drawing ------------------------------------------------------------
    def render(self) -> Text:
        width, height = self.size.width, self.size.height
        if width <= 0 or height <= 0:
            return Text("")
        s = self.state
        cw, ch = self.cell()
        chars = [[" "] * width for _ in range(height)]
        styles: list[list[Style | None]] = [[None] * width for _ in range(height)]

        def put(x: int, y: int, text: str, style: Style | None) -> None:
            if 0 <= x < width and 0 <= y < height:
                chars[y][x], styles[y][x] = text, style

        dim = Style(color="#555555")
        for r in range(s.rows):
            for c in range(s.cols):
                put(c * cw, r * ch, "·", dim)

        for index, p in enumerate(s.placements):
            x0, y0, x1, y1 = p.col * cw, p.row * ch, (p.col + p.cols) * cw, (p.row + p.rows) * ch
            selected = p.id == s.selected
            color = PALETTE[index % len(PALETTE)]
            fill = Style(color="white", bgcolor=color)
            border = Style(color="#ffd75f" if selected else "#a0a8b0", bgcolor=color, bold=selected)
            for y in range(y0, y1):
                for x in range(x0, x1):
                    put(x, y, " ", fill)
            boxed = (y1 - y0) >= 3 and (x1 - x0) >= 4
            if boxed:
                tl, tr, bl, br, hz, vt = "╔╗╚╝═║" if selected else "┌┐└┘─│"
                for x in range(x0 + 1, x1 - 1):
                    put(x, y0, hz, border)
                    put(x, y1 - 1, hz, border)
                for y in range(y0 + 1, y1 - 1):
                    put(x0, y, vt, border)
                    put(x1 - 1, y, vt, border)
                put(x0, y0, tl, border), put(x1 - 1, y0, tr, border)
                put(x0, y1 - 1, bl, border), put(x1 - 1, y1 - 1, br, border)
            cls = s.registry.get(p.module)
            title = cls.title if cls else f"? {p.module}"
            lines = [title, f"{p.rows}×{p.cols} {s.size_label(p)}", p.id]
            inset = 1 if boxed else 0
            first = y0 + (1 if boxed else 0)
            room = (y1 - inset) - first
            for i, line in enumerate(lines[:max(0, room)]):
                for j, letter in enumerate(line[: max(0, x1 - x0 - 2 * inset - 1)]):
                    put(x0 + inset + 1 + j, first + i, letter, Style(color="white", bgcolor=color, bold=(i == 0)))
            if selected:
                put(x1 - 1, y1 - 1, "◢", Style(color="#ffd75f", bgcolor=color, bold=True))

        if self.ghost:
            row, col, rows, cols, valid = self.ghost
            style = Style(color="#5fff87" if valid else "#ff5f5f", bold=True)
            for y in range(row * ch, (row + rows) * ch):
                for x in range(col * cw, (col + cols) * cw):
                    put(x, y, "▒", style)

        text = Text(no_wrap=True, overflow="crop")
        for y in range(height):
            x = 0
            while x < width:
                run = x
                while run < width and styles[y][run] == styles[y][x]:
                    run += 1
                text.append("".join(chars[y][x:run]), style=styles[y][x])
                x = run
            if y < height - 1:
                text.append("\n")
        return text


class LayoutEditor(App):
    TITLE = "modernDash · layout editor"
    CSS = """
    #side { width: 32; padding: 0 1; border-left: solid $primary; }
    #add { height: auto; max-height: 11; }
    #sizes { height: auto; }
    #info { height: 5; margin-top: 1; }
    .h { text-style: bold; margin-top: 1; }
    #side Button { width: 1fr; }
    #gridrow { height: auto; }
    """
    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("q", "quit_editor", "Quit"),
        Binding("delete,backspace", "remove", "Remove"),
        Binding("right_square_bracket", "size(1)", "Next size"),
        Binding("left_square_bracket", "size(-1)", "Prev size"),
        Binding("up", "move(-1,0)", "Move", show=False),
        Binding("down", "move(1,0)", "Move", show=False),
        Binding("left", "move(0,-1)", "Move", show=False),
        Binding("right", "move(0,1)", "Move", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.registry, self.load_errors = discover()
        self.state = EditorState(self.config.get("layout", {}), self.registry)
        self.state.dirty = False
        self.canvas = Canvas(self.state)
        self._add_ids: dict[str, str] = {}
        self._quit_armed = False

    # -- layout of the screen -----------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            yield self.canvas
            with VerticalScroll(id="side"):
                yield Static("Add a module", classes="h")
                with VerticalScroll(id="add"):
                    for i, (name, cls) in enumerate(sorted(self.registry.items())):
                        self._add_ids[f"add-{i}"] = name
                        yield button(f"+ {cls.title}", id=f"add-{i}")
                yield Static("", id="info")
                yield Static("Size", classes="h")
                yield Vertical(id="sizes")
                yield button("Remove module", id="remove", variant="error")
                yield Static("", id="gridinfo", classes="h")
                with Horizontal(id="gridrow"):
                    yield button("Rows −", id="rows-dec")
                    yield button("Rows +", id="rows-inc")
                with Horizontal(id="gridrow2"):
                    yield button("Cols −", id="cols-dec")
                    yield button("Cols +", id="cols-inc")
                yield Static("", classes="h")
                yield button("Save  (ctrl+s)", id="save", variant="success")
                yield button("Reset to default", id="reset")
                yield button("Quit  (q)", id="quit")
        yield Footer()

    async def on_mount(self) -> None:
        self.canvas.focus()
        if self.load_errors:
            self.notify("; ".join(f"{f}: {e}" for f, e in self.load_errors.items()),
                        title="Modules failed to load", severity="error")
        for warning in self.state.warnings:
            self.notify(warning, severity="warning")
        await self.refresh_sidebar()

    # -- sidebar ------------------------------------------------------------
    async def refresh_sidebar(self) -> None:
        s = self.state
        p = s.get(s.selected)
        info = self.query_one("#info", Static)
        sizes = self.query_one("#sizes", Vertical)
        await sizes.remove_children()
        if p is None:
            info.update("Click a module to select it.\nDrag to move, drag ◢ to resize,\nright-click to cycle sizes.")
        else:
            cls = s.registry.get(p.module)
            info.update(f"{cls.title if cls else p.module}\nid: {p.id}\n"
                        f"row {p.row + 1}, col {p.col + 1}\n{p.rows}×{p.cols} ({s.size_label(p)})")
            await sizes.mount(*[
                SizeButton(f"{label}  {r}×{c}", r, c, (r, c) == (p.rows, p.cols))
                for label, r, c in s.allowed_sizes(p)
            ])
        self.query_one("#gridinfo", Static).update(f"Grid {s.rows} rows × {s.cols} cols")

    async def on_canvas_changed(self, _: Canvas.Changed) -> None:
        self._quit_armed = False
        await self.refresh_sidebar()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        s, bid = self.state, event.button.id or ""
        if isinstance(event.button, SizeButton) and s.selected:
            if not s.resize(s.selected, event.button.size_rows, event.button.size_cols):
                self.notify("That size doesn't fit there.", severity="warning")
        elif bid in self._add_ids:
            if s.add(self._add_ids[bid]) is None:
                self.notify("No free space for that module. Make room or enlarge the grid.", severity="warning")
        elif bid == "remove" and s.selected:
            s.remove(s.selected)
        elif bid in ("rows-dec", "rows-inc", "cols-dec", "cols-inc"):
            dr = {"rows-dec": -1, "rows-inc": 1}.get(bid, 0)
            dc = {"cols-dec": -1, "cols-inc": 1}.get(bid, 0)
            if not s.set_grid(s.rows + dr, s.cols + dc):
                self.notify("The grid can't shrink past a placed module (or exceed 40).", severity="warning")
        elif bid == "save":
            self.action_save()
        elif bid == "reset":
            s.load(copy.deepcopy(DEFAULT_LAYOUT))
        elif bid == "quit":
            self.action_quit_editor()
        self.canvas.refresh()
        self._quit_armed = False
        await self.refresh_sidebar()
        self.canvas.focus()

    # -- actions ------------------------------------------------------------
    def action_save(self) -> None:
        try:
            save_layout(self.state.to_layout())
        except OSError as error:
            self.notify(f"Could not save: {error}", severity="error")
            return
        self.state.dirty = False
        self.notify("Layout saved. A running dashboard updates by itself.")

    def action_quit_editor(self) -> None:
        if self.state.dirty and not self._quit_armed:
            self._quit_armed = True
            self.notify("Unsaved changes. Press q again to discard them, or ctrl+s to save.", severity="warning")
            return
        self.exit()

    async def action_remove(self) -> None:
        if self.state.selected:
            self.state.remove(self.state.selected)
            self.canvas.refresh()
            await self.refresh_sidebar()

    async def action_size(self, step: int) -> None:
        if self.state.selected and not self.state.cycle_size(self.state.selected, step):
            self.notify("No other size fits there.", severity="warning")
        self.canvas.refresh()
        await self.refresh_sidebar()

    async def action_move(self, drow: int, dcol: int) -> None:
        p = self.state.get(self.state.selected)
        if p:
            self.state.move(p.id, p.row + drow, p.col + dcol)
            self.canvas.refresh()
            await self.refresh_sidebar()
