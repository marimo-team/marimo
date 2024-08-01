from dataclasses import dataclass

from marimo._plugins.ui._core.ui_element import UIElement


@dataclass
class Args:
    ...


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
