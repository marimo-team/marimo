# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Dict, Final, Iterator, Optional, Sequence

from marimo._output.formatters.structures import format_structure
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.stateless.flex import hstack, vstack
from marimo._plugins.stateless.json_output import json_output
from marimo._plugins.ui._core.ui_element import UIElement


# Frontend type is a tuple (index, value update)
# Python type is a sequence of values, one for each UI element
@mddoc
class array(UIElement[Dict[str, JSONType], Sequence[object]]):
    """
    An array of UI elements.

    Use an array to

    - create a dynamic number of UI elements at runtime
    - group together logically related UI elements
    - keep the number of global variables in your program small

    Access the values of the elements using the `value` attribute of the array
    (`array.value`).

    The elements in the array can be accessed using square brackets
    (`array[index]`) and embedded in other marimo outputs. You can also
    iterate over the UI elements using the `in` operator (`for element in
    array`).

    Note: The UI elements in the array are clones of the original elements:
    interacting with the array will _not_ update the original elements, and
    vice versa.

    **Examples.**

    A heterogeneous collection of UI elements:

    ```python
    array = mo.ui.array([mo.ui.slider(1, 10), mo.ui.text(), mo.ui.date()])
    ```

    Get the values of the `slider`, `text`, and `date` elements via
    `array.value`:

    ```python
    # array.value returns a list with the values of the elements
    array.value
    ```

    Access and output a UI element in the array:

    ```python
    mo.md(f"This is a slider: array[0]")
    ```

    Some number of UI elements, determined at runtime:

    ```python
    mo.ui.array([mo.ui.slider(1, 10) for _ in range random.randint(4, 8)])
    ```

    **Attributes.**

    - `value`: a list containing the values of the array's entries
    - `elements`: a list of the wrapped elements (clones of the originals)

    **Initialization Args.**

    - `elements`: the UI elements to include
    - `label`: a descriptive name for the array
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-dict"

    def __init__(
        self,
        elements: Sequence[UIElement[Any, Any]],
        *,
        label: str = "",
        on_change: Optional[Callable[[Sequence[object]], None]] = None,
    ) -> None:
        self._elements = [e._clone() for e in elements]
        self._label = label
        slotted_html = json_output(
            json_data=format_structure(self._elements),
            name="array" if not label else label,
        )
        super().__init__(
            component_name=array._name,
            initial_value={
                str(index): e._initial_value_frontend
                for index, e in enumerate(self._elements)
            },
            label=label,
            args={
                "element-ids": {
                    e._id: str(i) for i, e in enumerate(self._elements)
                },
            },
            slotted_html=slotted_html.text,
            on_change=on_change,
        )

        for i, element in enumerate(self._elements):
            element._register_as_view(self, key=str(i))

    @property
    def elements(self) -> Sequence[UIElement[JSONType, object]]:
        return self._elements

    def _convert_value(self, value: dict[str, JSONType]) -> Sequence[object]:
        if self._initialized:
            for k, v in value.items():
                element = self._elements[int(k)]
                # only call update if the value has changed
                if element._value_frontend != v:
                    element._update(v)
        return [e._value for e in self._elements]

    def _clone(self) -> array:
        return array(
            elements=self.elements,
            label=self._label,
            on_change=self._on_change,
        )

    def __len__(self) -> int:
        return len(self.elements)

    def __getitem__(self, key: int) -> UIElement[JSONType, object]:
        return self.elements[key]

    def __iter__(self) -> Iterator[UIElement[JSONType, object]]:
        return self.elements.__iter__()

    def __reversed__(self) -> Iterator[UIElement[JSONType, object]]:
        return self.elements.__reversed__()

    def __contains__(self, item: UIElement[JSONType, object]) -> bool:
        return item in self.elements

    def hstack(self, **kwargs: Any) -> Html:
        """
        Stack the elements horizontally.

        For kwargs, see `marimo.hstack`.
        """
        return hstack(items=self.elements, **kwargs)

    def vstack(self, **kwargs: Any) -> Html:
        """
        Stack the elements vertically.

        For kwargs, see `marimo.vstack`.
        """
        return vstack(items=self.elements, **kwargs)
