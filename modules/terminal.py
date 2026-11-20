"""Terminal keyboard input used to exit the full-screen dashboard."""

from __future__ import annotations

import sys

if sys.platform == "win32":
    import msvcrt

    class KeyWatcher:
        def __enter__(self) -> KeyWatcher:
            return self

        def __exit__(self, *_exc) -> None:
            del _exc

        def pressed(self) -> bool:
            if msvcrt.kbhit():
                msvcrt.getch()
                return True
            return False
else:
    import select
    import termios
    import tty

    class KeyWatcher:
        def __enter__(self) -> KeyWatcher:
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            return self

        def __exit__(self, *_exc) -> None:
            del _exc
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

        def pressed(self) -> bool:
            if select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.read(1)
                return True
            return False
