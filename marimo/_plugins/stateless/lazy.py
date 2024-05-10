# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Coroutine, Final, Union

from marimo._output.formatting import as_html
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.functions import EmptyArgs, Function


@dataclass
class LoadResponse:
    html: str


@mddoc
class lazy(UIElement[bool, bool]):
    """Lazy load a component until it is visible.

    Use `mo.lazy` to defer rendering of an item until it's visible. This is
    useful for loading expensive components only when they are needed, e.g.,
    only when an accordion or tab is opened.

    The argument to `mo.lazy` can be an object to render lazily, or a function
    that returns the object to render (that is, functions are lazily
    evaluated). The function can be synchronous or asynchronous.
    Using a function is useful when the item to render is
    the result of a database query or some other expensive operation.

    **Examples.**

    Create a lazy-loaded tab:

    ```python
    tabs = mo.ui.tabs(
        {"Overview": tab1, "Charts": mo.lazy(expensive_component)}
    )
    ```

    Create a lazy-loaded accordion:

    ```python
    accordion = mo.ui.accordion({"Charts": mo.lazy(expensive_component)})
    ```

    Usage with async functions:

    ```python
    async def expensive_component(): ...


    mo.lazy(expensive_component)
    ```


    **Initialization Args.**

    - `element`: object or callable that returns content to be lazily loaded
    - `show_loading_indicator`: a boolean, whether to show a loading
        indicator while the content is being loaded.
        Default is `False`.
    """

    _name: Final[str] = "marimo-lazy"

    def __init__(
        self,
        element: Union[
            Callable[[], object],
            object,
            Callable[[], Coroutine[None, None, object]],
        ],
        show_loading_indicator: bool = False,
    ) -> None:
        self._element = element

        super().__init__(
            component_name=self._name,
            initial_value=False,
            label="",
            args={
                "show-loading-indicator": show_loading_indicator,
            },
            on_change=None,
            functions=(
                Function(
                    name=self.load.__name__,
                    arg_cls=EmptyArgs,
                    function=self.load,
                ),
            ),
        )

    def _convert_value(self, value: bool) -> bool:
        return value

    async def load(self, _args: EmptyArgs) -> LoadResponse:
        if callable(self._element) and not isinstance(
            self._element, UIElement
        ):
            el = self._element()
            if asyncio.iscoroutine(el):
                el = await el
            return LoadResponse(html=as_html(el).text)
        else:
            return LoadResponse(html=as_html(self._element).text)
