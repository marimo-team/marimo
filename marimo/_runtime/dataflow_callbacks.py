# Copyright 2026 Marimo. All rights reserved.
"""Kernel-side dataflow API state and handlers.

The dataflow API (see ``development_docs/dataflow_api.md``) attaches one or
more ``DataflowSseConsumer``s to a session and drives the kernel via the
``ScopedRunCommand`` family of control messages. This module owns the
kernel-resident state for that API: per-consumer subscriptions, the
schema cache, and the post-run broadcast that turns a finished kernel run
into ``DataflowVarNotification``s on the wire.

It is invoked exclusively from the kernel process; ``DataflowSseConsumer``
lives on the host side and never imports this module.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from marimo import _loggers as loggers
from marimo._messaging.notification import (
    CompletedRunNotification,
    DataflowSchemaNotification,
    DataflowVarErrorNotification,
    DataflowVarNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.commands import (
    GetDataflowSchemaCommand,
    RemoveDataflowSubscriptionsCommand,
    ScopedRunCommand,
    SetDataflowSubscriptionsCommand,
    UpdateUIElementCommand,
)
from marimo._types.ids import UIElementId

if TYPE_CHECKING:
    from marimo._runtime.runtime import Kernel

LOGGER = loggers.marimo_logger()


@dataclass(frozen=True)
class DataflowScope:
    """Pruning hint passed through ``set_ui_element_value`` to the runner.

    Carries the subscription closure and the set of overridden inputs so
    the kernel can shrink its reactive cell set when no non-dataflow
    consumer is observing the run. The kernel layer treats both fields
    as advisory — empty ``subscribed`` means "do not prune."
    """

    subscribed: frozenset[str]
    overridden_inputs: frozenset[str]


class DataflowCallbacks:
    """Owns the kernel's per-consumer dataflow subscriptions and broadcasts.

    The kernel constructs one ``DataflowCallbacks`` and registers its
    handlers on the request handler. Subscriptions accumulate as
    ``DataflowSseConsumer``s attach; the post-run broadcast emits one
    ``DataflowVarNotification`` per (consumer, subscribed var) pair so
    every consumer sees fresh values regardless of which consumer's
    request triggered the run.
    """

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self._subscriptions: dict[str, frozenset[str]] = {}
        self._schema_id: str = uuid4().hex
        self._seq: int = 0
        # Set for the duration of a scoped run so the on-finish hook can
        # tag emitted ``dataflow-var`` events with the originating run id.
        # ``None`` means "this run came from somewhere else (editor, init)";
        # the hook synthesizes an editor-tagged run id in that case.
        self._current_run_id: str | None = None

    @property
    def subscriptions(self) -> dict[str, frozenset[str]]:
        return self._subscriptions

    @property
    def schema_id(self) -> str:
        return self._schema_id

    def union_subscriptions(self) -> frozenset[str]:
        """Union of subscribed variables across every attached consumer."""
        if not self._subscriptions:
            return frozenset()
        return frozenset().union(*self._subscriptions.values())

    # ------------------------------------------------------------------
    # Control-command handlers
    # ------------------------------------------------------------------

    async def set_subscriptions(
        self, request: SetDataflowSubscriptionsCommand
    ) -> None:
        self._subscriptions[request.consumer_id] = frozenset(request.subscribed)
        LOGGER.debug(
            "Dataflow consumer %s subscribed to %s",
            request.consumer_id,
            sorted(request.subscribed),
        )
        broadcast_notification(CompletedRunNotification())

    async def remove_subscriptions(
        self, request: RemoveDataflowSubscriptionsCommand
    ) -> None:
        self._subscriptions.pop(request.consumer_id, None)
        LOGGER.debug(
            "Dataflow consumer %s detached", request.consumer_id
        )
        broadcast_notification(CompletedRunNotification())

    async def get_schema(self, request: GetDataflowSchemaCommand) -> None:
        del request
        self._broadcast_schema()
        broadcast_notification(CompletedRunNotification())

    async def scoped_run(self, request: ScopedRunCommand) -> None:
        """Apply UI overrides, run reactively (optionally pruned), broadcast values.

        The reactive run fires the kernel's on-finish hooks; one of them is
        :meth:`on_kernel_run_finished`, which emits ``dataflow-var`` events
        tagged with ``request.run_id`` because we set it on the instance
        for the duration of the run.

        When ``inputs`` is empty (a pure subscription refresh), no reactive
        cells are queued and we emit values directly so the consumer still
        gets a snapshot.
        """
        self._subscriptions[request.consumer_id] = frozenset(request.subscribed)

        scope = DataflowScope(
            subscribed=frozenset(request.subscribed),
            overridden_inputs=frozenset(self._input_names_for(request.inputs)),
        )

        update_cmd = UpdateUIElementCommand(
            object_ids=list(request.inputs.keys()),
            values=list(request.inputs.values()),
            request=request.request,
        )

        previous_run_id = self._current_run_id
        self._current_run_id = request.run_id
        try:
            ran = await self._kernel.set_ui_element_value(
                update_cmd,
                notify_frontend=False,
                dataflow_scope=scope,
            )
            if not ran:
                # No cells were queued (empty inputs or no referrers): the
                # on-finish hook didn't fire, so emit a snapshot directly.
                self._broadcast_values_for_run(request.run_id)
        except Exception:
            LOGGER.exception("Scoped run failed")
        finally:
            self._current_run_id = previous_run_id

        broadcast_notification(CompletedRunNotification())

    # ------------------------------------------------------------------
    # Hook + post-run broadcast
    # ------------------------------------------------------------------

    def _broadcast_schema(self) -> None:
        """Snapshot the current schema and broadcast it on the kernel stream."""
        from marimo._dataflow.api import DATAFLOW_INPUT_MARKER
        from marimo._dataflow.schema import compute_dataflow_schema_from_globals
        from marimo._plugins.ui._core.ui_element import UIElement

        try:
            schema = compute_dataflow_schema_from_globals(
                graph=self._kernel.graph,
                globals_=self._kernel.globals,
                schema_id=self._schema_id,
            )
        except Exception:
            LOGGER.exception("Failed to compute dataflow schema")
            return

        # Internal mapping for the host-side bundle to translate
        # name-keyed wire requests into id-keyed kernel commands.
        input_object_ids: dict[str, str] = {}
        for name, val in self._kernel.globals.items():
            if isinstance(val, UIElement) and hasattr(
                val, DATAFLOW_INPUT_MARKER
            ):
                input_object_ids[name] = str(val._id)

        broadcast_notification(
            DataflowSchemaNotification(
                schema=_to_dict(schema),
                schema_id=self._schema_id,
                input_object_ids=input_object_ids,
            )
        )

    def _broadcast_values_for_run(self, run_id: str) -> None:
        """Emit ``dataflow-var`` events for every (consumer, subscribed var)."""
        if not self._subscriptions:
            return

        from marimo._dataflow.protocol import Kind
        from marimo._dataflow.serialize import infer_kind, serialize_value

        glbls = self._kernel.globals
        for consumer_id, vars_ in self._subscriptions.items():
            for var_name in sorted(vars_):
                self._seq += 1
                if var_name not in glbls:
                    broadcast_notification(
                        DataflowVarErrorNotification(
                            consumer_id=consumer_id,
                            run_id=run_id,
                            var_name=var_name,
                            error=(
                                f"variable {var_name!r} was not produced by "
                                "the graph"
                            ),
                        )
                    )
                    continue

                value = glbls[var_name]
                # UI elements: emit their materialized value, not the wrapper.
                from marimo._plugins.ui._core.ui_element import UIElement

                if isinstance(value, UIElement):
                    value = value.value

                kind = infer_kind(value)
                try:
                    json_value, ref = serialize_value(value, encoding="json")
                except Exception as exc:
                    broadcast_notification(
                        DataflowVarErrorNotification(
                            consumer_id=consumer_id,
                            run_id=run_id,
                            var_name=var_name,
                            error=f"failed to serialize {var_name!r}: {exc}",
                            traceback=traceback.format_exc(),
                        )
                    )
                    continue

                broadcast_notification(
                    DataflowVarNotification(
                        consumer_id=consumer_id,
                        run_id=run_id,
                        seq=self._seq,
                        var_name=var_name,
                        kind=kind.value if isinstance(kind, Kind) else str(kind),
                        encoding="json",
                        value=json_value,
                        ref=ref,
                    )
                )

    def on_kernel_run_finished(self, ctx: Any) -> None:
        """Kernel ``OnFinishHook`` that emits the post-run dataflow values.

        Registered once on the kernel's hooks. Fires after every reactive
        run regardless of who triggered it (dataflow client, editor slider
        drag, code execution). Skips when no consumer is subscribed so the
        hook is free in the no-dataflow case.
        """
        del ctx
        if not self._subscriptions:
            return
        run_id = self._current_run_id or f"editor-{int(time.time() * 1000)}"
        self._broadcast_values_for_run(run_id)

    def maybe_broadcast_schema(self) -> None:
        """Idempotent broadcast of the current schema.

        Called from the kernel's ``CompletedRunNotification`` path after
        the initial run so consumers see a schema before their first
        ``ScopedRunCommand``.
        """
        self._broadcast_schema()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _input_names_for(inputs: dict[UIElementId, Any]) -> set[str]:
        """Map UI-element ids back to the global names they're bound to.

        Used to populate ``DataflowScope.overridden_inputs`` so the runner
        can apply partial-override pruning. Falls back to an empty set if
        the runtime context isn't installed (e.g. during tests).
        """
        try:
            from marimo._runtime.context.types import get_context

            ctx = get_context()
        except Exception:
            return set()

        names: set[str] = set()
        registry = ctx.ui_element_registry
        for object_id in inputs:
            try:
                bound = registry.bound_names(object_id)
            except Exception:
                continue
            names.update(bound)
        return names


def _to_dict(struct: Any) -> dict[str, Any]:
    """msgspec → dict round-trip for embedding a schema in a notification."""
    import msgspec

    encoded = msgspec.json.encode(struct)
    return msgspec.json.decode(encoded)
