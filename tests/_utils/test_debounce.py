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
