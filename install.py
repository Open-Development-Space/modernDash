#!/usr/bin/env python3
"""Run ``python install.py`` once to set up the ``modernDash`` command."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import installer

if __name__ == "__main__":
    raise SystemExit(installer.run("install", sys.argv[1:]))
