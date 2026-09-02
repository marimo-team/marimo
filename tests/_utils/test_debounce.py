import time

from marimo._utils.debounce import debounce


def test_debounce_basic():
    invocation_count = 0

    @debounce(0.05)
    def my_fn():
        nonlocal invocation_count
        invocation_count += 1

    my_fn()
    my_fn()
    assert invocation_count == 1
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
    time.sleep(0.07)
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
    time.sleep(0.07)
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
    time.sleep(0.07)
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

    time.sleep(0.07)

    assert a.calls == ["a:1", "a:2"]
    assert b.calls == ["b:1", "b:2"]
