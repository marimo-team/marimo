# Copyright 2024 Marimo. All rights reserved.
"""Notification utilities for kernel messages.

CellNotificationUtils for cell-related broadcasts.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from marimo import _loggers as loggers

if TYPE_CHECKING:
    from collections.abc import Sequence

    import msgspec

from marimo._ast.cell import RuntimeStateType
from marimo._ast.toplevel import TopLevelHints, TopLevelStatus
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import (
    Error,
    MarimoInternalError,
    is_sensitive_error,
)
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.serde import serialize_kernel_message
from marimo._messaging.streams import output_max_bytes
from marimo._messaging.types import Stream
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.context.utils import get_mode
from marimo._types.ids import CellId_t

LOGGER = loggers.marimo_logger()


def broadcast_op(op: msgspec.Struct, stream: Optional[Stream] = None) -> None:
    """Broadcast an operation to the stream."""
    if stream is None:
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            LOGGER.debug("No context initialized.")
            return
        else:
            stream = ctx.stream

    try:
        stream.write(serialize_kernel_message(op))
    except Exception as e:
        LOGGER.exception(
            "Error serializing op %s: %s",
            op.__class__.__name__,
            e,
        )
        return


class CellNotificationUtils:
    """Utilities for broadcasting cell notifications."""

    @staticmethod
    def maybe_truncate_output(
        mimetype: KnownMimeType, data: str
    ) -> tuple[KnownMimeType, str]:
        if (size := sys.getsizeof(data)) > output_max_bytes():
            from marimo._output.md import md
            from marimo._plugins.stateless.callout import callout

            text = f"""
                <span class="text-error">**Your output is too large**</span>

                Your output is too large for marimo to show. It has a size
                of {size} bytes. Did you output this object by accident?

                If this limitation is a problem for you, you can configure
                the max output size by adding (eg)

                ```
                [tool.marimo.runtime]
                output_max_bytes = 10_000_000
                ```

                to your pyproject.toml, or with the environment variable
                `MARIMO_OUTPUT_MAX_BYTES`:

                ```
                export MARIMO_OUTPUT_MAX_BYTES=10_000_000
                ```

                Increasing the max output size may cause performance issues.
                If you run into problems, please reach out
                to us on [Discord](https://marimo.io/discord?ref=app) or
                [GitHub](https://github.com/marimo-team/marimo/issues).
                """

            warning = callout(
                md(text),
                kind="warn",
            )
            mimetype, data = warning._mime_()
        return mimetype, data

    @staticmethod
    def broadcast_output(
        channel: CellChannel,
        mimetype: KnownMimeType,
        data: str,
        cell_id: Optional[CellId_t],
        status: Optional[RuntimeStateType],
        stream: Stream | None = None,
    ) -> None:
        # Import here to avoid circular dependency
        from marimo._messaging.notifcation import CellOp

        mimetype, data = CellNotificationUtils.maybe_truncate_output(
            mimetype, data
        )
        cell_id = (
            cell_id if cell_id is not None else get_context().stream.cell_id
        )
        assert cell_id is not None
        broadcast_op(
            CellOp(
                cell_id=cell_id,
                output=CellOutput(
                    channel=channel,
                    mimetype=mimetype,
                    data=data,
                ),
                status=status,
            ),
            stream=stream,
        )

    @staticmethod
    def broadcast_empty_output(
        cell_id: Optional[CellId_t],
        status: Optional[RuntimeStateType],
        stream: Stream | None = None,
    ) -> None:
        # Import here to avoid circular dependency
        from marimo._messaging.notifcation import CellOp

        cell_id = (
            cell_id if cell_id is not None else get_context().stream.cell_id
        )
        assert cell_id is not None
        broadcast_op(
            CellOp(
                cell_id=cell_id,
                output=CellOutput.empty(),
                status=status,
            ),
            stream=stream,
        )

    @staticmethod
    def broadcast_console_output(
        channel: CellChannel,
        mimetype: KnownMimeType,
        data: str,
        cell_id: Optional[CellId_t],
        status: Optional[RuntimeStateType],
        stream: Stream | None = None,
    ) -> None:
        # Import here to avoid circular dependency
        from marimo._messaging.notifcation import CellOp

        mimetype, data = CellNotificationUtils.maybe_truncate_output(
            mimetype, data
        )
        cell_id = (
            cell_id if cell_id is not None else get_context().stream.cell_id
        )
        assert cell_id is not None
        broadcast_op(
            CellOp(
                cell_id=cell_id,
                console=CellOutput(
                    channel=channel,
                    mimetype=mimetype,
                    data=data,
                ),
                status=status,
            ),
            stream=stream,
        )

    @staticmethod
    def broadcast_status(
        cell_id: CellId_t,
        status: RuntimeStateType,
        stream: Stream | None = None,
    ) -> None:
        # Import here to avoid circular dependency
        from marimo._messaging.notifcation import CellOp

        if status != "running":
            broadcast_op(CellOp(cell_id=cell_id, status=status), stream)
        else:
            # Console gets cleared on "running"
            broadcast_op(
                CellOp(cell_id=cell_id, console=[], status=status),
                stream=stream,
            )

    @staticmethod
    def broadcast_error(
        data: Sequence[Error],
        clear_console: bool,
        cell_id: CellId_t,
    ) -> None:
        # Import here to avoid circular dependency
        from marimo._messaging.notifcation import CellOp

        console: Optional[list[CellOutput]] = [] if clear_console else None

        # In run mode, we don't want to broadcast the error. Instead we want to print the error to the console
        # and then broadcast a new error such that the data is hidden.
        safe_errors: list[Error] = []
        if get_mode() == "run":
            for error in data:
                # Skip non-sensitive errors
                if not is_sensitive_error(error):
                    safe_errors.append(error)
                    continue

                error_id = uuid4()
                LOGGER.error(
                    f"(error_id={error_id}) {error.describe()}",
                    extra={"error_id": error_id},
                )
                safe_errors.append(MarimoInternalError(error_id=str(error_id)))
        else:
            safe_errors = list(data)

        broadcast_op(
            CellOp(
                cell_id=cell_id,
                output=CellOutput.errors(safe_errors),
                console=console,
                status=None,
            )
        )

    @staticmethod
    def broadcast_stale(
        cell_id: CellId_t, stale: bool, stream: Stream | None = None
    ) -> None:
        # Import here to avoid circular dependency
        from marimo._messaging.notifcation import CellOp

        broadcast_op(CellOp(cell_id=cell_id, stale_inputs=stale), stream)

    @staticmethod
    def broadcast_serialization(
        cell_id: CellId_t,
        serialization: TopLevelStatus,
        stream: Stream | None = None,
    ) -> None:
        # Import here to avoid circular dependency
        from marimo._messaging.notifcation import CellOp

        status: Optional[TopLevelHints] = serialization.hint
        broadcast_op(
            CellOp(cell_id=cell_id, serialization=str(status)), stream
        )
