"""PyInstaller entry shim for DragonByte Z, the creator application."""

from __future__ import annotations

import sys

from tools.creator.app import main

if __name__ == "__main__":
    sys.exit(main())
