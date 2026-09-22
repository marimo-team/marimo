# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import threading
from unittest.mock import Mock

from marimo._messaging.notification import StartupProgressNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._session.consumer import SessionConsumer
from marimo._session.startup import SessionStartup


async def test_worker_output_reaches_consumers_on_the_session_loop() -> None:
    loop_thread = threading.current_thread()
    startup = SessionStartup()
    delivered = asyncio.Event()
    seen: list[tuple[threading.Thread, str | None]] = []
    consumer = Mock(spec=SessionConsumer)

    def notify(_message: bytes) -> None:
        progress = startup.view.startup_progress
        # Consumers observe a view that already includes the notification.
        seen.append(
            (
                threading.current_thread(),
                progress.phase if progress is not None else None,
            )
        )
        delivered.set()

    consumer.notify.side_effect = notify
    progress = StartupProgressNotification(phase="starting-kernel")
    with startup.subscribe(consumer):
        await asyncio.to_thread(startup.notify, progress)
        await asyncio.wait_for(delivered.wait(), 5)

    assert seen == [(loop_thread, "starting-kernel")]
    assert (
        deserialize_kernel_message(consumer.notify.call_args.args[0])
        == progress
    )
