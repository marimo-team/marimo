# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import signal
from unittest.mock import Mock

import pytest

from marimo._utils.signals import SigintHandler


def test_nested_deferral_replays_after_outermost_scope() -> None:
    callback = Mock()
    handler = SigintHandler(callback)

    with handler.defer():
        handler(signal.SIGINT, None)
        with handler.defer():
            handler(signal.SIGINT, None)
        callback.assert_not_called()

    callback.assert_called_once_with(signal.SIGINT, None)


def test_deferral_ends_before_raising_handler_runs() -> None:
    callback = Mock(side_effect=KeyboardInterrupt)
    handler = SigintHandler(callback)

    with pytest.raises(KeyboardInterrupt), handler.defer():
        handler(signal.SIGINT, None)

    # The old pending interrupt must not leak into a later write.
    with handler.defer():
        pass
    callback.assert_called_once_with(signal.SIGINT, None)

    with pytest.raises(KeyboardInterrupt):
        handler(signal.SIGINT, None)
    assert callback.call_count == 2


def test_deferral_replays_when_scope_raises() -> None:
    callback = Mock()
    handler = SigintHandler(callback)

    def fail_after_interrupt() -> None:
        handler(signal.SIGINT, None)
        raise RuntimeError("send failed")

    with pytest.raises(RuntimeError), handler.defer():
        fail_after_interrupt()

    callback.assert_called_once_with(signal.SIGINT, None)
