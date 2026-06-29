# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.notification import ConsumerCapabilities
from marimo._runtime import commands
from marimo._session.capabilities import (
    Capability,
    consumer_can,
    required_capability,
)

EDITOR = ConsumerCapabilities(edit=True, interact=True)
INTERACTOR = ConsumerCapabilities(edit=False, interact=True)
VIEWER = ConsumerCapabilities(edit=False, interact=False)


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


def test_unknown_command_fails_closed_to_edit() -> None:
    class MysteryCommand: ...

    assert required_capability(MysteryCommand) is Capability.EDIT


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
