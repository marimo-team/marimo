# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import Mock

from marimo._messaging.notification import StartupProgressNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._session.consumer import SessionConsumer
from marimo._session.startup import SessionStartup


def test_late_subscriber_receives_current_phase_then_live_progress() -> None:
    startup = SessionStartup()
    preparing = StartupProgressNotification(phase="preparing-environment")
    starting = StartupProgressNotification(phase="starting-kernel")
    first, second = Mock(spec=SessionConsumer), Mock(spec=SessionConsumer)

    with startup.subscribe(first):
        startup.notify(preparing)
    # Startup can advance while no browser is observing it.
    startup.notify(starting)
    with startup.subscribe(second):
        assert startup.view.startup_progress == starting

    assert [
        deserialize_kernel_message(call.args[0])
        for call in first.notify.call_args_list
    ] == [preparing]
    assert [
        deserialize_kernel_message(call.args[0])
        for call in second.notify.call_args_list
    ] == [starting]


def test_disconnecting_one_subscriber_preserves_the_other() -> None:
    startup = SessionStartup()
    first, second = Mock(spec=SessionConsumer), Mock(spec=SessionConsumer)
    progress = StartupProgressNotification(phase="preparing-environment")
    with startup.subscribe(second):
        with startup.subscribe(first):
            pass
        startup.notify(progress)
    first.notify.assert_not_called()
    assert (
        deserialize_kernel_message(second.notify.call_args.args[0]) == progress
    )
