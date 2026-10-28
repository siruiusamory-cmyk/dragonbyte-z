import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from tests.unit.test_workbench_staged_work import (
    _stage_every_provider,
    catalog,
    qapp,
    staged_shell,
)

STAGING_METHODS = ("unsaved_edit_count", "_palette_edit_count", "_staged_edit_count")


def _surfaces(window) -> dict[str, object]:
    return {name: host.content() or host for name, host in window._hosts.items()}


def _holds_unapplied_values(surface) -> bool:
    return any(callable(getattr(surface, name, None)) for name in STAGING_METHODS)


def test_every_shell_editor_that_holds_an_unapplied_value_registers_it(staged_shell):
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
    shell = staged_shell
    _stage_every_provider(shell)
    providers = shell.session._staged_work

    assert shell.session.unsaved_edit_count() == 5
    counts = [provider() for provider in providers]
    assert counts == [1, 2, 1, 1], counts
    assert sum(counts) == shell.session.unsaved_edit_count()
