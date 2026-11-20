"""Entry point for ``modernDash layout`` (the editor itself lives in layout_ui.py)."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def run_editor() -> int:
    try:
        from layout_ui import LayoutEditor
    except ModuleNotFoundError as error:
        if (error.name or "").split(".")[0] not in ("textual", "rich"):
            raise
        print(
            f"The layout editor needs the '{error.name}' package.\n"
            "Run `modernDash install` (it sets everything up), or: pip install textual",
            file=sys.stderr,
        )
        return 1
    LayoutEditor().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_editor())
