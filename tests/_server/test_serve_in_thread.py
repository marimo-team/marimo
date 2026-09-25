# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import threading
from unittest.mock import Mock

import pytest

from tests._server.conftest import serve_in_thread


@pytest.mark.parametrize(
    "failure", [RuntimeError("listener failed"), SystemExit(1)]
)
@pytest.mark.parametrize("body_fails", [False, True])
@pytest.mark.parametrize("shutdown_fails", [False, True])
def test_surfaces_worker_failure(
    monkeypatch, failure, body_fails, shutdown_fails
):
    started = threading.Event()
    worker = None
    body_error = ConnectionError("connection failed")

    def serve():
        nonlocal worker
        worker = threading.current_thread()
        started.set()
        raise failure

    shutdown_error = (
        RuntimeError("shutdown failed") if shutdown_fails else None
    )
    server = Mock(
        serve_forever=Mock(side_effect=serve),
        shutdown=Mock(side_effect=shutdown_error),
    )
    with pytest.raises(type(failure)) as exc:  # noqa: PT012
        with serve_in_thread(server):
            assert started.wait(timeout=5)
            assert worker is not None
            join = Mock(wraps=worker.join)
            monkeypatch.setattr(worker, "join", join)
            if body_fails:
                raise body_error

    assert exc.value is failure
    if shutdown_fails:
        assert exc.value.__context__ is shutdown_error
        if body_fails:
            assert shutdown_error.__context__ is body_error
    elif body_fails:
        assert exc.value.__context__ is body_error
    server.shutdown.assert_called_once_with()
    join.assert_called_once_with(timeout=5)
    assert not worker.is_alive()


@pytest.mark.parametrize("body_fails", [False, True])
@pytest.mark.parametrize("shutdown_fails", [False, True])
def test_joins_worker_on_exit(monkeypatch, body_fails, shutdown_fails):
    started = threading.Event()
    stopped = threading.Event()
    worker = None
    body_error = ValueError("test body failed")
    shutdown_error = RuntimeError("shutdown failed")

    def serve():
        nonlocal worker
        worker = threading.current_thread()
        started.set()
        assert stopped.wait(timeout=5)

    def shutdown():
        stopped.set()
        if shutdown_fails:
            raise shutdown_error

    server = Mock(
        serve_forever=Mock(side_effect=serve),
        shutdown=Mock(side_effect=shutdown),
    )
    caught = None
    try:
        with serve_in_thread(server):
            assert started.wait(timeout=5)
            assert worker is not None
            join = Mock(wraps=worker.join)
            monkeypatch.setattr(worker, "join", join)
            if body_fails:
                raise body_error
    except (ValueError, RuntimeError) as exc:
        caught = exc

    if shutdown_fails:
        assert caught is shutdown_error
        if body_fails:
            assert caught.__context__ is body_error
    elif body_fails:
        assert caught is body_error
    else:
        assert caught is None
    server.shutdown.assert_called_once_with()
    join.assert_called_once_with(timeout=5)
    assert not worker.is_alive()
