# Copyright 2026 Marimo. All rights reserved.
"""Tests for ThreadLocalStreamProxy and thread-local stream helpers."""

from __future__ import annotations

import io
import sys
import threading
from unittest.mock import MagicMock

from marimo._messaging.thread_local_streams import (
    ThreadLocalStreamProxy,
    clear_thread_local_streams,
    install_thread_local_proxies,
    set_thread_local_streams,
    uninstall_thread_local_proxies,
)

# ---------------------------------------------------------------------------
# ThreadLocalStreamProxy unit tests
# ---------------------------------------------------------------------------


class TestThreadLocalStreamProxy:
    def test_write_to_original_when_no_thread_local(self) -> None:
        original = io.StringIO()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")
        proxy.write("hello")
        assert original.getvalue() == "hello"

    def test_write_to_thread_local_stream(self) -> None:
        original = io.StringIO()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")

        thread_stream = io.StringIO()
        proxy._set_stream(thread_stream)
        proxy.write("hello")

        assert thread_stream.getvalue() == "hello"
        assert original.getvalue() == ""

    def test_clear_falls_back_to_original(self) -> None:
        original = io.StringIO()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")

        thread_stream = io.StringIO()
        proxy._set_stream(thread_stream)
        proxy.write("a")
        proxy._clear_stream()
        proxy.write("b")

        assert thread_stream.getvalue() == "a"
        assert original.getvalue() == "b"

    def test_thread_isolation(self) -> None:
        """Writes from different threads go to different streams."""
        original = io.StringIO()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")

        stream_a = io.StringIO()
        stream_b = io.StringIO()
        barrier = threading.Barrier(2)

        def thread_fn(stream: io.StringIO, label: str) -> None:
            proxy._set_stream(stream)
            barrier.wait()  # synchronise so both threads are active
            proxy.write(label)
            proxy.flush()

        t1 = threading.Thread(target=thread_fn, args=(stream_a, "A"))
        t2 = threading.Thread(target=thread_fn, args=(stream_b, "B"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert stream_a.getvalue() == "A"
        assert stream_b.getvalue() == "B"
        assert original.getvalue() == ""

    def test_unregistered_thread_uses_original(self) -> None:
        """Threads that never call _set_stream write to original."""
        original = io.StringIO()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")

        def thread_fn() -> None:
            proxy.write("unregistered")

        t = threading.Thread(target=thread_fn)
        t.start()
        t.join()

        assert original.getvalue() == "unregistered"

    def test_writelines(self) -> None:
        original = io.StringIO()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")
        proxy.writelines(["hello", " ", "world"])
        assert original.getvalue() == "hello world"

    def test_flush_delegates(self) -> None:
        original = MagicMock(spec=io.StringIO)
        original.flush = MagicMock()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")
        proxy.flush()
        original.flush.assert_called_once()

    def test_name_property(self) -> None:
        original = io.StringIO()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")
        assert proxy.name == "<stdout>"

    def test_writable(self) -> None:
        original = io.StringIO()
        proxy = ThreadLocalStreamProxy(original, "<stdout>")
        assert proxy.writable()
        assert not proxy.readable()
        assert not proxy.seekable()


# ---------------------------------------------------------------------------
# install / set / clear helper tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_install_thread_local_proxies_is_idempotent(self) -> None:
        """install_thread_local_proxies installs proxies and is idempotent."""
        try:
            install_thread_local_proxies()
            first_stdout = sys.stdout
            first_stderr = sys.stderr
            assert isinstance(first_stdout, ThreadLocalStreamProxy)
            assert isinstance(first_stderr, ThreadLocalStreamProxy)

            # Second call should be a no-op
            install_thread_local_proxies()
            assert sys.stdout is first_stdout
            assert sys.stderr is first_stderr
        finally:
            uninstall_thread_local_proxies()

    def test_set_and_clear_thread_local_streams(self) -> None:
        """set/clear thread local streams operate on proxies."""
        saved_stdout = sys.stdout
        saved_stderr = sys.stderr
        try:
            install_thread_local_proxies()

            mock_out = MagicMock()
            mock_err = MagicMock()
            set_thread_local_streams(mock_out, mock_err)

            proxy_out: ThreadLocalStreamProxy = sys.stdout  # type: ignore
            proxy_err: ThreadLocalStreamProxy = sys.stderr  # type: ignore
            assert proxy_out._get_stream() is mock_out
            assert proxy_err._get_stream() is mock_err

            clear_thread_local_streams()
            # After clear, should fall back to original
            assert proxy_out._get_stream() is saved_stdout
            assert proxy_err._get_stream() is saved_stderr
        finally:
            uninstall_thread_local_proxies()

    def test_set_noop_without_proxy(self) -> None:
        """set/clear are safe to call when proxies are not installed."""
        saved_stdout = sys.stdout
        saved_stderr = sys.stderr
        try:
            sys.stdout = io.StringIO()  # type: ignore
            sys.stderr = io.StringIO()  # type: ignore
            # Should not raise
            set_thread_local_streams(MagicMock(), MagicMock())
            clear_thread_local_streams()
        finally:
            sys.stdout = saved_stdout
            sys.stderr = saved_stderr


# ---------------------------------------------------------------------------
# Integration: multiple "sessions" in threads
# ---------------------------------------------------------------------------


def test_multi_session_no_deadlock() -> None:
    """Simulate two sessions in threads — no deadlock, correct routing."""
    original = io.StringIO()
    proxy = ThreadLocalStreamProxy(original, "<stdout>")

    results: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def session(name: str) -> None:
        buf = io.StringIO()
        proxy._set_stream(buf)
        barrier.wait()
        for _ in range(100):
            proxy.write(name)
        proxy.flush()
        results[name] = buf.getvalue()
        proxy._clear_stream()

    t1 = threading.Thread(target=session, args=("A",))
    t2 = threading.Thread(target=session, args=("B",))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert not t1.is_alive(), "Thread A deadlocked"
    assert not t2.is_alive(), "Thread B deadlocked"
    assert results["A"] == "A" * 100
    assert results["B"] == "B" * 100
    assert original.getvalue() == ""
