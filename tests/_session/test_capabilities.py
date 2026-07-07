# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import typing

import pytest

from marimo._messaging.notification import ConsumerCapabilities
from marimo._runtime import commands
from marimo._session.capabilities import (
    _EDIT_COMMANDS,
    _INTERACT_COMMANDS,
    _READ_COMMANDS,
    Capability,
    consumer_can,
    required_capability,
)

EDITOR = ConsumerCapabilities.EDITOR
INTERACTOR = ConsumerCapabilities.INTERACTOR
VIEWER = ConsumerCapabilities.VIEWER


def test_role_presets_have_expected_bits() -> None:
    # Everything else references the presets by name; pin their definitions
    # here so a change to the role bit-patterns cannot pass silently.
    assert (EDITOR.edit, EDITOR.interact) == (True, True)
    assert (INTERACTOR.edit, INTERACTOR.interact) == (False, True)
    assert (VIEWER.edit, VIEWER.interact) == (False, False)


def test_required_capability_classifies_commands() -> None:
    assert required_capability(commands.ExecuteCellsCommand) is Capability.EDIT
    assert (
        required_capability(commands.ExecuteScratchpadCommand)
        is Capability.EDIT
    )
    assert (
        required_capability(commands.UpdateUIElementCommand)
        is Capability.INTERACT
    )
    # InvokeFunctionCommand smuggles arbitrary user code (chat/lazy/panel),
    # so it is interact-tier, not read-tier.
    assert (
        required_capability(commands.InvokeFunctionCommand)
        is Capability.INTERACT
    )
    assert (
        required_capability(commands.CodeCompletionCommand) is Capability.READ
    )
    assert (
        required_capability(commands.PreviewDatasetColumnCommand)
        is Capability.READ
    )


def test_unknown_command_raises() -> None:
    class MysteryCommand: ...

    with pytest.raises(AssertionError, match="not classified"):
        required_capability(MysteryCommand)


def test_every_command_is_classified() -> None:
    """Every enforceable command must be deliberately tiered.

    A new command added to the `CommandMessage` union without a capability
    tier would default to `edit` at runtime, so this test forces the author
    to place it in exactly one of the three sets instead.
    """
    all_commands = set(typing.get_args(commands.CommandMessage))
    classified = _READ_COMMANDS | _INTERACT_COMMANDS | _EDIT_COMMANDS

    unclassified = all_commands - classified
    assert not unclassified, (
        "commands missing a capability tier in capabilities.py: "
        f"{sorted(c.__name__ for c in unclassified)}"
    )

    stale = classified - all_commands
    assert not stale, (
        "commands classified in capabilities.py but not in CommandMessage: "
        f"{sorted(c.__name__ for c in stale)}"
    )

    for pair in (
        (_READ_COMMANDS, _INTERACT_COMMANDS),
        (_READ_COMMANDS, _EDIT_COMMANDS),
        (_INTERACT_COMMANDS, _EDIT_COMMANDS),
    ):
        assert not (pair[0] & pair[1]), (
            "a command is classified in more than one tier: "
            f"{sorted(c.__name__ for c in pair[0] & pair[1])}"
        )


def test_viewer_can_only_read() -> None:
    assert consumer_can(VIEWER, commands.CodeCompletionCommand) is True
    assert consumer_can(VIEWER, commands.PreviewDatasetColumnCommand) is True
    # Viewers cannot invoke functions (could run user code / touch the fs).
    assert consumer_can(VIEWER, commands.InvokeFunctionCommand) is False
    assert consumer_can(VIEWER, commands.UpdateUIElementCommand) is False
    assert consumer_can(VIEWER, commands.ExecuteCellsCommand) is False


def test_interactor_can_interact_not_edit() -> None:
    assert consumer_can(INTERACTOR, commands.UpdateUIElementCommand) is True
    assert consumer_can(INTERACTOR, commands.InvokeFunctionCommand) is True
    assert consumer_can(INTERACTOR, commands.ExecuteCellsCommand) is False


def test_editor_can_do_everything() -> None:
    assert consumer_can(EDITOR, commands.ExecuteCellsCommand) is True
    assert consumer_can(EDITOR, commands.UpdateUIElementCommand) is True
    assert consumer_can(EDITOR, commands.InvokeFunctionCommand) is True
