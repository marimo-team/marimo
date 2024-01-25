from marimo._utils.disposable import Disposable


def test_disposable():
    was_action_called = False

    def action():
        nonlocal was_action_called
        was_action_called = True

    disposable = Disposable(action)
    assert not disposable.is_disposed()
    disposable.dispose()
    assert was_action_called
    assert disposable.is_disposed()


def test_disposable_empty():
    empty_disposable = Disposable.empty()
    assert not empty_disposable.is_disposed()
    empty_disposable.dispose()
    assert empty_disposable.is_disposed()
