"""The entry point: the window, a build job child, the version, or the self-test."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from tools.webfoot.release_identity import release_identity

from .model.jobs import JOB_FLAG, run_job


def configuration_directory() -> Path:
    from PySide6.QtCore import QStandardPaths

    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    return Path(location) if location else Path.home() / ".dragonbyte-z"


def _start_logging(directory: Path) -> None:
    try:
        (directory / "logs").mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=directory / "logs" / "dragonbyte-z.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        return
    sys.excepthook = lambda kind, value, trace: logging.getLogger("dragonbyte-z").error(
        "unhandled error", exc_info=(kind, value, trace)
    )


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    identity = release_identity()
    if "--version" in arguments:
        print(identity.display)
        return 0
    if JOB_FLAG in arguments:
        return run_job(Path(arguments[arguments.index(JOB_FLAG) + 1]))

    parser = argparse.ArgumentParser(prog="dragonbyte-z", add_help=False)
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

        window = MainWindow(identity.display, options.workdir / "settings", quiet=True)
        window.show()
        return run_selftest(app, window, options)
    settings_directory = configuration_directory()
    _start_logging(settings_directory)
    window = MainWindow(identity.display, settings_directory)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
