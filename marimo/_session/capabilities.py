# Copyright 2026 Marimo. All rights reserved.
"""Capability enforcement: which capability a kernel command requires.

The capability a command requires is the minimum a consumer must hold to issue
it. `read` is the floor every consumer holds; `interact` drives shared-kernel UI
state; `edit` mutates the notebook. Unknown commands fail closed to `edit`.
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


def required_capability(command_type: type) -> Capability:
    """The minimum capability required to issue a command of this type.

    Unknown commands fail closed to `edit` so a new command is never silently
    granted to viewers before it is classified here.
    """
    if command_type in _READ_COMMANDS:
        return Capability.READ
    if command_type in _INTERACT_COMMANDS:
        return Capability.INTERACT
    return Capability.EDIT


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
