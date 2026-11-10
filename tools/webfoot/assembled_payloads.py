"""Assemble the tracked payload sources a composed build reads.

The payload sources under ``patchsource`` are tracked assembly; their ``.bin``
siblings are build output and are ignored by Git. A fresh clone therefore has
none of them, and every consumer (the sprite limit guard, the dialogue
presentation payloads, the pause page's own seam) reads the ``.bin``. This
module runs the tracked assembly scripts for any payload whose binary is
missing, so the documented build command works from a fresh clone given only
the private ROM inputs and the devkitARM toolchain the build already needs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent / "patchsource"

SCRIPTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("log1-sprite-limits/assemble.ps1", ("budget.bin", "bank.bin", "law.bin")),
    ("log1-bf-presentation/assemble.ps1", ("presentation.bin", "portrait.bin")),
    ("log1-bf-presentation/assemble-box.ps1",
     ("box.bin", "bf-box-geometry.bin", "bf-box-strips.bin", "bf-box-window.bin",
      "text.bin")),
)

POWERSHELL = Path(r"C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")


class AssemblyError(RuntimeError):
    """An assembled payload could not be produced from its tracked source."""


def _shell() -> str:
    return str(POWERSHELL) if POWERSHELL.is_file() else "powershell"


def ensure_assembled() -> None:
    """Run the tracked assembler for every payload whose binary is missing."""
    for script, outputs in SCRIPTS:
        directory = SOURCE_ROOT / Path(script).parent
        absent = tuple(name for name in outputs if not (directory / name).is_file())
        if not absent:
            continue
        completed = subprocess.run(
            [_shell(), "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(SOURCE_ROOT / script)],
            cwd=str(directory), capture_output=True, text=True)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip().splitlines()
            raise AssemblyError(
                f"{script} could not assemble {', '.join(absent)} "
                f"(exit {completed.returncode}): "
                f"{detail[-1] if detail else 'no output'}")
        still = tuple(name for name in absent if not (directory / name).is_file())
        if still:
            raise AssemblyError(f"{script} did not produce {', '.join(still)}")
