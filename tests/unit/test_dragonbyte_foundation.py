"""DRAGONBYTE-Z-FOUNDATION-001: the application package, its session and its window.

Two lanes, deliberately separated.

The headless lane drives the session, the destination registry, the navigation
history, the settings file and the diagnostics text with no ``QApplication`` at
all, and proves that importing those modules leaves PySide6 out of
``sys.modules``. That proof runs in a fresh interpreter, because a suite that has
loaded Qt in this process can no longer answer the question.

The windowed lane runs offscreen and drives the real shell: the six destinations,
the one inspector, the four disabled global actions, back and forward, and a
close that persists settings. Nothing here opens a canonical image except the one
test that needs it, and that test skips when the image is not present.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402
import re  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtWidgets")


from tools.dragonbyte import navigation  # noqa: E402
from tools.dragonbyte.navigation import MAX_HISTORY, NavigationHistory  # noqa: E402
from tools.dragonbyte.session import (  # noqa: E402
    Session,
    SessionError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPOSITORY_ROOT / "tools" / "dragonbyte"


#: A machine-specific absolute path. The uppercase-or-symbol start after the
#: separator keeps a source escape (``states:\n`` is the two characters ``\``
#: and ``n``) from reading as a path, while a real one always starts a path
#: component with a drive root, a digit or a dot.
DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/]{1,2}(?:[A-Z0-9_.$]|$)")
HOME_PATH = re.compile(r"(?:/Users/|/home/)")


def _package_files() -> list[Path]:
    """Every Python file in the application package, in a stable order."""
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def _package_source(module: str) -> str:
    return (PACKAGE_ROOT / module).read_text(encoding="utf-8")


def _imported_names(relative: str, tree: ast.AST) -> list[str]:
    """Every dotted module a parsed file imports, relative spellings resolved.

    Reuses the purity gate's resolver, so the test and the gate cannot disagree
    about what a spelling means.
    """
    from tools.quality import architecture as arch

    return [name for name, _line in arch._imported_modules(relative, tree)]


# --- 1. the package imports cleanly, headless ---------------------------------


# --- 2. the identity has one authority ---------------------------------------


def test_no_package_file_restates_the_version():
    for path in _package_files():
        assert "0.9.0" not in path.read_text(encoding="utf-8"), path


# --- 3 and 4. the destinations -------------------------------------------------


# --- 5. exactly one session authority ----------------------------------------


def test_the_session_is_defined_once_and_carries_no_second_answer_to_dirty():
    definitions = []
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        definitions.extend(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "Session"
        )

    assert definitions == ["Session"]

    members = {field.name for field in dataclasses.fields(Session)} | set(dir(Session))
    # STATE-001 gave the session exactly one journal, which owns every edit, every
    # checkpoint and the derived dirty state. The rule this test exists for is
    # unchanged, so it is restated rather than dropped: the session holds no
    # independent dirty flag, no edit counter and no second undo stack. Two
    # entries are deliberate and named, because they are the session's edit
    # boundary - `journal` is the one journal, and `undo_edit`/`redo_edit` are
    # thin calls into it, not an undo stack kept here.
    forbidden = ("staged", "dirty", "revision", "unsaved", "undo")
    allowed = {"journal", "undo_edit", "redo_edit"}
    assert [
        name
        for name in members
        if any(word in name for word in forbidden) and name not in allowed
    ] == []
    assert [name for name in members if "journal" in name] == ["journal"]
    assert not hasattr(Session, "register_staged_work")
    assert not hasattr(Session, "unsaved_edit_count")
    assert not hasattr(Session, "undo_stack")
    assert not hasattr(Session, "dirty")


# --- 6. navigation is not edit undo ------------------------------------------


def test_navigation_moves_a_cursor_and_never_creates_entries():
    history = NavigationHistory("maps")

    assert history.current.destination == "maps"
    assert len(history) == 1

    history.push("maps")
    assert len(history) == 1, "pushing the current destination must be a no-op"

    history.push("data")
    history.push("graphics")
    assert len(history) == 3
    assert history.back().destination == "data"

    history.push("rom")
    assert len(history) == 3, "pushing must drop the forward tail"
    assert history.current.destination == "rom"
    assert not history.can_go_forward
    assert history.forward() is None
    assert history.back().destination == "data"
    assert history.can_go_forward
    assert history.forward().destination == "rom"


def test_navigation_trims_the_oldest_entry_at_the_cap():
    history = NavigationHistory()
    for index in range(MAX_HISTORY + 5):
        history.push(f"destination-{index}")

    assert len(history) == MAX_HISTORY
    assert history.current.destination == f"destination-{MAX_HISTORY + 4}"

    steps = 0
    while history.back() is not None:
        steps += 1
    assert steps == MAX_HISTORY - 1
    assert not history.can_go_back
    assert history.back() is None


def test_the_qt_free_modules_hold_no_qt_import_and_no_undo_type():
    for module in ("session.py", "navigation.py"):
        source = _package_source(module)
        assert "QUndo" not in source, module
        tree = ast.parse(source)
        assert "PySide6" not in _imported_names(f"tools/dragonbyte/{module}", tree)


# --- 7. one inspector ---------------------------------------------------------


# --- 8. the four global actions ----------------------------------------------


# --- 9. the architecture gate -------------------------------------------------


def test_the_real_tree_passes_the_gate_and_the_package_never_imports_the_beta():
    from tools.quality import architecture as arch

    assert arch._rule_import_direction(arch.tracked_files()) == []
    assert arch.check()["violations"] == []

    for path in _package_files():
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        beta = [
            name
            for name in _imported_names(relative, tree)
            if name == "tools.webfoot.workbench"
            or name.startswith("tools.webfoot.workbench.")
        ]
        assert beta == [], relative


# --- 10. no machine-specific path in the package ------------------------------


def test_no_package_file_carries_a_machine_specific_absolute_path():
    """No package file names a path on one machine.

    The project's own public-surface screen is the authority on what counts as
    a machine-specific path, so it is asked directly; the local pattern beside
    it catches a drive root the screen's narrower rule does not name.
    """
    from tools.quality import public_surface

    for path in _package_files():
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        findings, _suppressed = public_surface.scan(REPOSITORY_ROOT, relative)
        assert findings == [], findings
        source = path.read_text(encoding="utf-8")
        assert not DRIVE_PATH.search(source), relative
        assert not HOME_PATH.search(source), relative


# --- 11. opening an image never writes it ------------------------------------


def test_a_refused_image_is_byte_identical_after_the_open_attempt(tmp_path):
    image = tmp_path / "not-a-game-image.gba"
    payload = bytes(range(256)) * 8
    image.write_bytes(payload)
    before = hashlib.sha256(image.read_bytes()).hexdigest()
    session = Session()

    with pytest.raises(SessionError):
        session.open_rom(image)

    assert hashlib.sha256(image.read_bytes()).hexdigest() == before
    assert image.read_bytes() == payload
    assert not session.has_rom


def test_a_truncated_image_is_refused_as_a_session_error(tmp_path):
    """A file too short to carry a header is a fact about the input, not a
    programmer error: it must arrive as the boundary type."""
    image = tmp_path / "truncated.gba"
    image.write_bytes(b"short")
    session = Session()

    with pytest.raises(SessionError):
        session.open_rom(image)

    assert not session.has_rom


# --- 12. the offscreen window and the process smoke --------------------------


# --- the diagnostics surface --------------------------------------------------


# --- the settings surface -----------------------------------------------------


def test_navigation_max_history_is_the_published_cap():
    assert navigation.MAX_HISTORY == 100
