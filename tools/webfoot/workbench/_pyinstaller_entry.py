"""PyInstaller entry shim for Postboy Advance.

PyInstaller freezes a script, not a `-m package` invocation, so this file just
calls the workbench's real `main()`. It exists only for the frozen build; the
normal launch paths (`python -m tools.webfoot.workbench`, the `postboy-advance`
console script, the `.cmd`) do not use it.
"""

from __future__ import annotations

import sys

from tools.webfoot.workbench.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
