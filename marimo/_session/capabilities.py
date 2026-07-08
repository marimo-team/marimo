# Copyright 2026 Marimo. All rights reserved.
"""Capability enforcement: which capability a kernel command requires.

The capability a command requires is the minimum a consumer must hold to issue
it. `read` is the floor every consumer holds; `interact` drives shared-kernel UI
state; `edit` mutates the notebook. Every command is triaged into exactly one
tier; an unclassified command raises rather than defaulting.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from marimo._runtime import commands

if TYPE_CHECKING:
    from marimo._messaging.notification import ConsumerCapabilities


class Capability(Enum):
    READ = "read"
    INTERACT = "interact"
    EDIT = "edit"


# InvokeFunctionCommand is interact-tier, not read-tier: although table/df
# paging is read-shaped, the same command also invokes arbitrary user code
# (mo.ui.chat model calls, mo.lazy loaders, from_panel callbacks) and touches
# the filesystem (file_browser). Per-function read-tiering is a kernel-side
# follow-up; until then a pure spectator's table is frozen on page 1.
_INTERACT_COMMANDS: frozenset[type] = frozenset(
    {
        commands.UpdateUIElementCommand,
        commands.ModelCommand,
        commands.InvokeFunctionCommand,
    }
)

# Read-tier commands never mutate notebook or reactive state and never invoke
# user code: completions and data/secret previews and listings.
_READ_COMMANDS: frozenset[type] = frozenset(
    {
        commands.CodeCompletionCommand,
        commands.PreviewDatasetColumnCommand,
        commands.PreviewSQLTableCommand,
        commands.ListSQLTablesCommand,
        commands.ListSQLSchemasCommand,
        commands.ValidateSQLCommand,
        commands.ListDataSourceConnectionCommand,
        commands.StorageListEntriesCommand,
        commands.StorageDownloadCommand,
        commands.ListSecretKeysCommand,
        commands.GetCacheInfoCommand,
    }
)

# Edit-tier commands mutate the notebook, its reactive state, or the kernel
# lifecycle. Enumerated explicitly so a deliberate edit-tier command is
# distinguishable from one that was never triaged: the latter raises in
# `required_capability` instead of being silently classified as edit.
_EDIT_COMMANDS: frozenset[type] = frozenset(
    {
        commands.CreateNotebookCommand,
        commands.RenameNotebookCommand,
        commands.ExecuteCellsCommand,
        commands.ExecuteScratchpadCommand,
        commands.ExecuteStaleCellsCommand,
        commands.DebugCellCommand,
        commands.DeleteCellCommand,
        commands.SyncGraphCommand,
        commands.UpdateCellConfigCommand,
        commands.InstallPackagesCommand,
        commands.UpdateUserConfigCommand,
        commands.RefreshSecretsCommand,
        commands.ClearCacheCommand,
        commands.StopKernelCommand,
    }
)


def required_capability(command_type: type) -> Capability:
    """The minimum capability required to issue a command of this type.

    Every command in the `CommandMessage` union is triaged into exactly one
    tier, enforced by `test_every_command_is_classified`. A command that
    reaches here unclassified is a programming error (a new command that was
    never triaged), so fail loud rather than silently granting or denying it.
    Raising is itself fail-closed: callers surface it as a refusal, not a grant.
    """
    if command_type in _READ_COMMANDS:
        return Capability.READ
    if command_type in _INTERACT_COMMANDS:
        return Capability.INTERACT
    if command_type in _EDIT_COMMANDS:
        return Capability.EDIT
    raise AssertionError(
        f"Command {command_type.__name__} is not classified into a capability tier."
    )


def consumer_can(
    capabilities: ConsumerCapabilities, command_type: type
) -> bool:
    """Whether a consumer with `capabilities` may issue this command type."""
    required = required_capability(command_type)
    if required is Capability.READ:
        return True
    if required is Capability.INTERACT:
        return capabilities.interact
    return capabilities.edit
