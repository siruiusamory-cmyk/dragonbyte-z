"""What the application remembers between runs: emulator, recent projects, folders."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import subprocess

SETTINGS_FILE = "settings.json"
DEFAULT_EMULATORS = (
    Path(r"C:\Program Files\mGBA\mGBA.exe"),
    Path(r"C:\Program Files (x86)\mGBA\mGBA.exe"),
)
RECENT_LIMIT = 8


@dataclass
class AppSettings:
    emulator: str = ""
    last_directory: str = ""
    recent: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, directory: Path) -> "AppSettings":
        try:
            document = json.loads(
                (Path(directory) / SETTINGS_FILE).read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return cls()
        if not isinstance(document, dict):
            return cls()
        recent = document.get("recent")
        return cls(
            emulator=str(document.get("emulator") or ""),
            last_directory=str(document.get("last_directory") or ""),
            recent=[item for item in recent if isinstance(item, str)]
            if isinstance(recent, list)
            else [],
        )

    def save(self, directory: Path) -> None:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            (Path(directory) / SETTINGS_FILE).write_text(
                json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8"
            )
        except OSError:
            return

    def remember_project(self, directory: Path) -> None:
        entry = str(Path(directory).resolve())
        self.recent = [entry] + [item for item in self.recent if item != entry]
        del self.recent[RECENT_LIMIT:]
        self.last_directory = str(Path(directory).resolve().parent)

    def emulator_path(self) -> Path | None:
        """The configured emulator, or an installed mGBA, or nothing."""
        candidates = ([Path(self.emulator)] if self.emulator else []) + list(
            DEFAULT_EMULATORS
        )
        return next((path for path in candidates if path.is_file()), None)


def launch_emulator(emulator: Path, rom: Path, script: Path | None = None) -> subprocess.Popen:
    extra = ["--script", str(script)] if script else []
    return subprocess.Popen([str(emulator), *extra, str(rom)], cwd=str(Path(emulator).parent))
