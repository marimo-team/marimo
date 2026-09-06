import contextvars
import inspect
import time
from collections.abc import Callable

from marimo._utils.debounce import debounce


def _wait_until(predicate: Callable[[], bool], timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_debounce_basic():
    invocation_count = 0

    @debounce(0.05)
    def my_fn():
        nonlocal invocation_count
        invocation_count += 1

    my_fn()
    my_fn()
    assert invocation_count == 1
    assert _wait_until(lambda: True, timeout=0.06)
    time.sleep(0.06)
    my_fn()
    assert invocation_count == 2


def test_debounce_with_args():
    captured_arg = None

    @debounce(0.05)
    def my_arg_fn(x: int):
        nonlocal captured_arg
        captured_arg = x

    my_arg_fn(1)
    my_arg_fn(2)
    assert captured_arg == 1
    time.sleep(0.06)
    my_arg_fn(3)
    assert captured_arg == 3


def test_debounce_trailing():
    calls: list[int] = []

    @debounce(0.05, trailing=True)
    def my_fn(x: int) -> None:
        calls.append(x)

    my_fn(1)
    my_fn(2)
    assert calls == [1]
    assert _wait_until(lambda: calls == [1, 2], timeout=1.0)
    assert calls == [1, 2]


def test_debounce_trailing_coalesces():
    calls: list[int] = []

    @debounce(0.05, trailing=True)
    def my_fn(x: int) -> None:
        calls.append(x)

    my_fn(1)
    my_fn(2)
    my_fn(3)
    my_fn(4)
    assert calls == [1]
    assert _wait_until(lambda: calls == [1, 4], timeout=1.0)
    assert calls == [1, 4]


def test_debounce_cancel():
    calls: list[int] = []

    @debounce(0.05, trailing=True)
    def my_fn(x: int) -> None:
        calls.append(x)

    my_fn(1)
    my_fn(2)
    assert calls == [1]
    my_fn.cancel()
    time.sleep(0.08)
    assert calls == [1]


def test_debounce_method_per_instance():
    class Item:
        def __init__(self, name: str) -> None:
            self.name = name
            self.calls: list[str] = []

        @debounce(0.05, trailing=True)
        def record(self, msg: str) -> None:
            self.calls.append(f"{self.name}:{msg}")

    a = Item("a")
    b = Item("b")

    a.record("1")
    b.record("1")
    a.record("2")
    b.record("2")

    assert a.calls == ["a:1"]
    assert b.calls == ["b:1"]

    assert _wait_until(
        lambda: a.calls == ["a:1", "a:2"] and b.calls == ["b:1", "b:2"],
        timeout=1.0,
    )
    assert a.calls == ["a:1", "a:2"]
    assert b.calls == ["b:1", "b:2"]


def test_debounce_preserves_metadata_and_signature():
    @debounce(0.05, trailing=True)
    def documented_fn(a: int, b: str = "foo") -> None:
        """Sample docstring for testing metadata preservation."""

    assert documented_fn.__name__ == "documented_fn"
    assert documented_fn.__doc__ == "Sample docstring for testing metadata preservation."
    assert hasattr(documented_fn, "__wrapped__")

    sig = inspect.signature(documented_fn)
    params = list(sig.parameters.values())
    assert len(params) == 2
    assert params[0].name == "a"
    assert params[0].annotation is int
    assert params[1].name == "b"
    assert params[1].default == "foo"


def test_debounce_slots_class_method():
    class SlottedWorker:
        __slots__ = ("__weakref__", "calls")

        def __init__(self) -> None:
            self.calls: list[int] = []

        @debounce(0.05, trailing=True)
        def process(self, value: int) -> None:
            self.calls.append(value)

    worker = SlottedWorker()
    worker.process(1)
    worker.process(2)
    assert worker.calls == [1]

    assert _wait_until(lambda: worker.calls == [1, 2], timeout=1.0)
    assert worker.calls == [1, 2]


def test_debounce_strict_slots_without_weakref():
    class StrictSlotsWorker:
        __slots__ = ("calls",)  # explicitly no __weakref__

        def __init__(self) -> None:
            self.calls: list[int] = []

        @debounce(0.05, trailing=True)
        def process(self, value: int) -> None:
            self.calls.append(value)

    worker = StrictSlotsWorker()
    worker.process(10)
    worker.process(20)
    assert worker.calls == [10]

    assert _wait_until(lambda: worker.calls == [10, 20], timeout=1.0)
    assert worker.calls == [10, 20]


def test_debounce_trailing_propagates_latest_contextvars():
    request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
        "request_id", default="none"
    )
    observed_contexts: list[str] = []

    @debounce(0.05, trailing=True)
    def log_request(action: str) -> None:
        observed_contexts.append(f"{request_id.get()}:{action}")

    token1 = request_id.set("req-1")
    log_request("leading")  # executed immediately under req-1
    request_id.reset(token1)

    token2 = request_id.set("req-2")
    log_request("trailing")  # queued under req-2
    request_id.reset(token2)

    assert observed_contexts == ["req-1:leading"]

    assert _wait_until(
        lambda: observed_contexts == ["req-1:leading", "req-2:trailing"],
        timeout=1.0,
    )
    assert observed_contexts == ["req-1:leading", "req-2:trailing"]
