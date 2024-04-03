# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Final, Union

from marimo._output.formatting import as_html
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.functions import EmptyArgs, Function


@dataclass
class LoadResponse:
    html: str


@mddoc
class lazy(UIElement[None, None]):
    """Lazy load a component until it is visible.

    This be a marimo element or any HTML content. This is useful for
    loading expensive components only when they are needed.

    This defers any frontend rendering until the content is visible.

    If the content is a function, it will additionally be lazily evaluated
    in Python as well. This is useful for database queries or other
    expensive operations.

    **Examples.**

    Create a lazy-loaded tab:

    ```python
    tabs = mo.ui.tabs({
        "Overview": tab1,
        "Charts": mo.lazy(expensive_component)
    })
    ```

    Create a lazy-loaded accordion:

    ```python
    accordion = mo.ui.accordion({
        "Charts": mo.lazy(expensive_component)
    })
    ```

    **Initialization Args.**

    - `element`: content or callable that returns content to be lazily loaded
    - `show_spinner`: a boolean, whether to show a loading spinner while.
        Default is `False`.
    """

    _name: Final[str] = "marimo-lazy"

    def __init__(
        self,
        element: Union[Callable[[], object], object],
        show_spinner: bool = False,
    ) -> None:
        self._element = element

        super().__init__(
            component_name=self._name,
            initial_value=None,
            label="",
            args={
                "show-spinner": show_spinner,
            },
            on_change=lambda _: None,
            functions=(
                Function(
                    name=self.load.__name__,
                    arg_cls=EmptyArgs,
                    function=self.load,
                ),
            ),
        )

    def _convert_value(self, value: None) -> None:
        return value

    def load(self, _args: EmptyArgs) -> LoadResponse:
        if callable(self._element) and not isinstance(
            self._element, UIElement
        ):
            el = self._element()
            return LoadResponse(html=as_html(el).text)
        else:
            return LoadResponse(html=as_html(self._element).text)
