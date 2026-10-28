"""WB-SAFE-001: every shell editor that can hold an unapplied value registers it.

The count behind the close prompt, the title and the status bar is
`Session.unsaved_edit_count`, and an editor is visible to it only by calling
`Session.register_staged_work`. This census enumerates the editors the shell
actually builds, so an editor that stages work without registering is a failure
here rather than a silent close.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from tests.unit.test_workbench_state_and_errors import (
    _stage_every_provider,
    catalog,
    qapp,
    staged_shell,
)

STAGING_METHODS = ("unsaved_edit_count", "_palette_edit_count", "_staged_edit_count")


def _surfaces(window) -> dict[str, object]:
    """Each editor the shell hosts, by the name the strip shows."""
    return {
        name: host.content() or host
        for name, host in window._hosts.items()
    }


def _holds_unapplied_values(surface) -> bool:
    """Whether this surface answers a count of work no write has taken."""
    return any(callable(getattr(surface, name, None)) for name in STAGING_METHODS)


def test_every_shell_editor_that_holds_an_unapplied_value_registers_it(staged_shell):
    """The census: the staging editors are exactly the ones with a provider."""
    session = staged_shell.session
    registered = {getattr(provider, "__self__", None) for provider in session._staged_work}
    staging = {
        name: surface
        for name, surface in _surfaces(staged_shell.window).items()
        if _holds_unapplied_values(surface)
    }

    assert set(staging) == {"Maps", "Graphics", "Inspector", "Scene"}
    unregistered = sorted(
        name for name, surface in staging.items() if surface not in registered
    )
    assert unregistered == [], unregistered
    assert len(session._staged_work) == len(staging)


def test_every_registered_provider_answers_its_own_staged_item(staged_shell):
    """A registration that answers nothing would be a census entry, not a count."""
    shell = staged_shell
    _stage_every_provider(shell)
    providers = shell.session._staged_work

    assert shell.session.unsaved_edit_count() == 5
    counts = [provider() for provider in providers]
    assert counts == [1, 2, 1, 1], counts
    assert sum(counts) == shell.session.unsaved_edit_count()
