# Copyright 2026 Marimo. All rights reserved.
"""Bounded delivery of attachment snapshots through normal kernel dispatch."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import msgspec

from marimo._core import protocol
from marimo._messaging.agents import AgentInfo, connection_namespace
from marimo._messaging.notification import FunctionCallResultNotification
from marimo._messaging.serde import try_deserialize_kernel_notification_name
from marimo._runtime.commands import InvokeFunctionCommand
from marimo._server.host.agents import connected_agents
from marimo._session.extensions.types import EventAwareExtension
from marimo._types.ids import RequestId

if TYPE_CHECKING:
    from marimo._core.host import Host
    from marimo._core.notebook import Notebook
    from marimo._core.stream import RoutedEvent
    from marimo._messaging.types import KernelMessage
    from marimo._session.session import Session


@dataclass
class _Subscription:
    notebook: Notebook
    session: Session
    subscription_id: str
    latest: tuple[AgentInfo, ...]
    sent: tuple[AgentInfo, ...] | None = None
    in_flight: RequestId | None = None
    revision: int = 0


class _ConnectionListener(EventAwareExtension):
    def __init__(self, owner: AgentConnections) -> None:
        super().__init__()
        self._owner = owner

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        self._owner.on_notification_sent(session, notification)

    def on_detach(self) -> None:
        session = self._session
        super().on_detach()
        if session is not None:
            self._owner.remove_session(session)


class AgentConnections:
    """Keep one in-flight update and the latest state per observer."""

    def __init__(self, host: Host) -> None:
        self._subscriptions: dict[str, _Subscription] = {}
        self._calls: dict[RequestId, str] = {}
        self._sessions: dict[int, ExitStack] = {}
        self._unsubscribe = host.subscribe(self._observe)

    def subscribe(
        self, notebook: Notebook, session: Session, subscription_id: str
    ) -> None:
        self.unsubscribe(session, subscription_id)
        if subscription_id in self._subscriptions:
            raise ValueError("Subscription belongs to another runtime")
        if id(session) not in self._sessions:
            stack = ExitStack()
            stack.enter_context(session.scoped(_ConnectionListener(self)))
            self._sessions[id(session)] = stack
        subscription = _Subscription(
            notebook, session, subscription_id, connected_agents(notebook)
        )
        self._subscriptions[subscription_id] = subscription
        self._dispatch(subscription)

    def unsubscribe(self, session: Session, subscription_id: str) -> None:
        subscription = self._subscriptions.get(subscription_id)
        if subscription is None or subscription.session is not session:
            return
        self._subscriptions.pop(subscription_id)
        if subscription.in_flight is not None:
            self._calls.pop(subscription.in_flight, None)
        if not any(s.session is session for s in self._subscriptions.values()):
            stack = self._sessions.pop(id(session), None)
            if stack is not None:
                stack.close()

    def close(self) -> None:
        self._unsubscribe()
        for subscription in tuple(self._subscriptions.values()):
            self.unsubscribe(
                subscription.session, subscription.subscription_id
            )

    def remove_session(self, session: Session) -> None:
        for subscription in tuple(self._subscriptions.values()):
            self.unsubscribe(session, subscription.subscription_id)

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        if (
            try_deserialize_kernel_notification_name(notification)
            != FunctionCallResultNotification.name
        ):
            return
        result = msgspec.json.decode(
            notification, type=FunctionCallResultNotification
        )
        subscription_id = self._calls.get(result.function_call_id)
        subscription = self._subscriptions.get(subscription_id or "")
        if subscription is None or subscription.session is not session:
            return
        self._calls.pop(result.function_call_id)
        subscription.in_flight = None
        if not result.found:
            self.unsubscribe(session, subscription.subscription_id)
        else:
            self._dispatch(subscription)

    def _observe(self, event: RoutedEvent) -> None:
        if not isinstance(
            event.event,
            (
                protocol.AttachmentEvent,
                protocol.AttachmentRemovedEvent,
                protocol.NotebookRemovedEvent,
                protocol.RuntimeRemovedEvent,
                protocol.RuntimeEvent,
            ),
        ):
            return
        if isinstance(
            event.event, protocol.RuntimeEvent
        ) and event.event.data.runtime.status not in {"failed", "terminating"}:
            return
        notebook_id = (
            event.event.data.id
            if isinstance(event.event, protocol.NotebookRemovedEvent)
            else event.notebook_id
        )
        for subscription in tuple(self._subscriptions.values()):
            if subscription.notebook.id != notebook_id:
                continue
            if isinstance(
                event.event,
                (
                    protocol.NotebookRemovedEvent,
                    protocol.RuntimeRemovedEvent,
                    protocol.RuntimeEvent,
                ),
            ):
                self.unsubscribe(
                    subscription.session, subscription.subscription_id
                )
                continue
            subscription.latest = connected_agents(subscription.notebook)
            self._dispatch(subscription)

    def _dispatch(self, subscription: _Subscription) -> None:
        if (
            subscription.in_flight is not None
            or subscription.sent == subscription.latest
        ):
            return
        call_id = RequestId(uuid4().hex)
        subscription.in_flight = call_id
        subscription.sent = subscription.latest
        subscription.revision += 1
        self._calls[call_id] = subscription.subscription_id
        subscription.session.put_control_request(
            InvokeFunctionCommand(
                function_call_id=call_id,
                namespace=connection_namespace(subscription.subscription_id),
                function_name="update",
                args={
                    "revision": subscription.revision,
                    "agents": msgspec.to_builtins(list(subscription.latest)),
                },
            ),
            from_consumer_id=None,
        )
