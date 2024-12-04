import io
from contextlib import redirect_stderr

from marimo._plugins.ui._core.ui_element import UIElement


class Element(UIElement[int, int]):
    _name: str = "element"

    def __init__(self) -> None:
        super().__init__(
            component_name=Element._name,
            initial_value=0,
            label=None,
            args={},
            on_change=self.on_change_method,
        )

    def on_change_method(self, value: int) -> None:
        del value
        ...

    def _convert_value(self, value: int) -> int:
        return value


def test_ui_element_clone() -> None:
    element = Element()
    clone = element._clone()

    assert element._id != clone._id

    # the on_change method should be bound to the clone instance, not the
    # original instance
    assert element._on_change is not None
    assert clone._on_change is not None
    assert id(element._on_change.__self__) != id(clone._on_change.__self__)


def test_bool_ui_element() -> None:
    element = Element()
    expected_warning = (
        "The truth value of a UIElement is always True. You "
        "probably want to call `.value` instead."
    )
    with io.StringIO() as buf, redirect_stderr(buf):
        assert bool(element) is True
        assert buf.getvalue() == expected_warning

    with io.StringIO() as buf, redirect_stderr(buf):
        res = not element
        del res
        assert buf.getvalue() == expected_warning


def test_ui_element_random_id() -> None:
    element1 = Element()
    element2 = Element()

    assert element1._random_id != element2._random_id

    class AnotherElement(UIElement[int, int]):
        _name: str = "another_element"

        def __init__(self) -> None:
            super().__init__(
                component_name=AnotherElement._name,
                initial_value=0,
                label=None,
                args={},
                on_change=None,
            )

        def _convert_value(self, value: int) -> int:
            return value

    another_element = AnotherElement()
    assert element1._random_id != another_element._random_id
