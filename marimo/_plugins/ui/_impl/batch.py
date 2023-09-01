# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Dict, Final, Optional

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement


# - Frontend type is a dict {label => value update}
# - Python type is a dict mapping label -> value
class _batch_base(UIElement[Dict[str, JSONType], Dict[str, object]]):
    """
    A batch of named UI elements represented by HTML text.
    """

    _name: Final[str] = "marimo-dict"

    def __init__(
        self,
        html: Html,
        elements: dict[str, UIElement[JSONType, object]],
        label: str = "",
        on_change: Optional[Callable[[Dict[str, object]], None]] = None,
    ) -> None:
        self._elements = elements
        super().__init__(
            component_name=_batch_base._name,
            initial_value={
                key: e._initial_value_frontend
                for key, e in self._elements.items()
            },
            label=label,
            args={
                "element-ids": {
                    e._id: key for key, e in self._elements.items()
                },
            },
            slotted_html=html.text,
            on_change=on_change,
        )

    @property
    def elements(self) -> dict[str, UIElement[JSONType, object]]:
        return self._elements

    def _convert_value(self, value: dict[str, JSONType]) -> dict[str, object]:
        if self._initialized:
            for k, v in value.items():
                self._elements[k]._update(v)
        return {
            key: wrapped_element._value
            for key, wrapped_element in self._elements.items()
        }


@mddoc
class batch(_batch_base):
    """
    Convert an HTML object with templated text into a UI element.

    A `batch` is a UI element that wraps other UI elements, and is
    represented by custom HTML or markdown. You can create
    a `batch` by calling the `batch()` method on `Html` objects.

    **Example.**

    ```python3
    user_info = mo.md(
        '''
        - What's your name?: {name}
        - When were you born?: {birthday}
        '''
    ).batch(name=mo.ui.text(), birthday=mo.ui.date())
    ```

    In this example, `user_info` is a UI Element whose output is markdown
    and whose value is a dict with keys `'name'` and '`birthday`'
    (and values equal to the values of their corresponding elements).

    You can also instantiate this class directly:

    ```python3
    markdown = mo.md(
        '''
        - What's your name?: {name}
        - When were you born?: {birthday}
        '''
    )
    batch = mo.ui.batch(
        markdown, {"name": mo.ui.text(), "birthday": mo.ui.date()}
    )
    ```

    **Attributes.**

    - `value`: a `dict` of the batched elements' values
    - `elements`: a `dict` of the batched elements (clones of the originals)
    - `on_change`: optional callback to run when this element's value changes

    **Initialization Args.**

    - html: a templated `Html` object
    - elements: the UI elements to interpolate into the HTML template
    - `on_change`: optional callback to run when this element's value changes
    """

    def __init__(
        self,
        html: Html,
        elements: dict[str, UIElement[Any, Any]],
        on_change: Optional[Callable[[Dict[str, object]], None]] = None,
    ) -> None:
        self._html = html
        elements = {key: element._clone() for key, element in elements.items()}
        super().__init__(
            html=Html(self._html.text.format(**elements)),
            elements=elements,
            on_change=on_change,
        )

    def _clone(self) -> batch:
        return batch(html=self._html, elements=self.elements)
