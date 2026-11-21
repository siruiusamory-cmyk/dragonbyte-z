"""The entry point: the window, a build job child, the version, or the self-test."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import shutil
import sys

from tools.webfoot.release_identity import identity_document, release_identity

from .model.jobs import JOB_FLAG, run_job

LEGACY_APPLICATION_NAME = "DragonByte Z"
LEGACY_FALLBACK_DIRECTORY = ".dragonbyte-z"


def configuration_directory() -> Path:
    from PySide6.QtCore import QCoreApplication, QStandardPaths

    def location(fallback: str) -> Path:
        found = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
        return Path(found) if found else Path.home() / fallback

    directory = location(".postboy-advance")
    name = QCoreApplication.applicationName()
    QCoreApplication.setApplicationName(LEGACY_APPLICATION_NAME)
    try:
        legacy = location(LEGACY_FALLBACK_DIRECTORY)
    finally:
        QCoreApplication.setApplicationName(name)
    adopt_legacy_settings(directory, legacy)
    return directory


def adopt_legacy_settings(directory: Path, legacy: Path) -> None:
    """Copy the pre-rename settings to the new location once; the legacy copy stays."""
    if directory.exists() or not legacy.is_dir():
        return
    partial = directory.with_name(directory.name + ".partial")
    try:
        shutil.rmtree(partial, ignore_errors=True)
        shutil.copytree(legacy, partial)
        partial.rename(directory)
    except OSError:
        logging.getLogger("postboy-advance").warning(
            "could not copy settings from %s to %s", legacy, directory, exc_info=True
        )
        shutil.rmtree(partial, ignore_errors=True)


def _start_logging(directory: Path):
    try:
        (directory / "logs").mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=directory / "logs" / "postboy-advance.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        return None
    from .ui.front_door import ErrorHook

    sys.excepthook = hook = ErrorHook()
    return hook


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    identity = release_identity()
    if "--version" in arguments:
        print(identity.display)
        return 0
    if JOB_FLAG in arguments:
        return run_job(Path(arguments[arguments.index(JOB_FLAG) + 1]))

    parser = argparse.ArgumentParser(prog="postboy-advance", add_help=False)
    parser.add_argument("--selftest", type=Path, metavar="REPORT")
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--play-seconds", type=int, default=0)
    options, _rest = parser.parse_known_args(arguments)

    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow

    app = QApplication([sys.argv[0]])
    app.setApplicationName(identity.product_name)
    app.setApplicationVersion(identity.version)
    if options.selftest is not None:
        if options.rom is None or options.workdir is None:
            print("error: --selftest needs --rom and --workdir", file=sys.stderr)
            return 2
        from .selftest import run_selftest

        window = MainWindow(identity.display, options.workdir / "settings", quiet=True,
                            identity=identity_document())
        window.show()
        return run_selftest(app, window, options)
    settings_directory = configuration_directory()
    hook = _start_logging(settings_directory)
    window = MainWindow(identity.display, settings_directory, identity=identity_document())
    if hook is not None:
        hook.window = window
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
