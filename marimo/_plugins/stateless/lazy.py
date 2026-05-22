# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from marimo import _loggers
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html, is_non_interactive
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.functions import EmptyArgs, Function

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

LOGGER = _loggers.marimo_logger()


@dataclass
class LoadResponse:
    html: str


def _is_lazy_callable(element: object) -> bool:
    return callable(element) and not isinstance(element, UIElement)


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

    Note:
        In non-interactive contexts (ipynb and PDF exports), `mo.lazy`
        renders its element eagerly and returns the resolved HTML
        directly, since no kernel is available to invoke the lazy load
        function. Async elements cannot be resolved from a synchronous
        constructor; they fall back to the lazy widget. HTML export
        keeps the lazy widget as-is.

    Examples:
        Create a lazy-loaded tab:
        ```python
        tabs = mo.ui.tabs(
            {"Overview": tab1, "Charts": mo.lazy(expensive_component)}
        )
        ```

        Create a lazy-loaded accordion:
        ```python
        accordion = mo.accordion({"Charts": mo.lazy(expensive_component)})
        ```

        Usage with async functions:
        ```python
        async def expensive_component(): ...


        mo.lazy(expensive_component)
        ```

    Args:
        element (Union[Callable[[], object], object, Callable[[], Coroutine[None, None, object]]]):
            Object or callable that returns content to be lazily loaded.
        show_loading_indicator (bool, optional): Whether to show a loading indicator
            while the content is being loaded. Defaults to False.
    """

    _name: Final[str] = "marimo-lazy"

    def __new__(
        cls,
        element: Callable[[], object]
        | object
        | Callable[[], Coroutine[None, None, object]],
        show_loading_indicator: bool = False,  # noqa: ARG004
    ) -> Any:
        if is_non_interactive():
            resolved = _resolve_eagerly(element)
            if resolved is not None:
                return resolved
        return super().__new__(cls)

    def __init__(
        self,
        element: Callable[[], object]
        | object
        | Callable[[], Coroutine[None, None, object]],
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
                    name="load",
                    arg_cls=EmptyArgs,
                    function=self._load,
                ),
            ),
        )

    def _convert_value(self, value: bool) -> bool:
        return value

    async def _load(self, _args: EmptyArgs) -> LoadResponse:
        if _is_lazy_callable(self._element):
            el = self._element()  # type: ignore[operator]
        else:
            el = self._element
        if asyncio.iscoroutine(el):
            el = await el
        return LoadResponse(html=as_html(el).text)


def _resolve_eagerly(element: object) -> Html | None:
    if asyncio.iscoroutine(element):
        element.close()
        return None

    if not _is_lazy_callable(element):
        return as_html(element)

    if asyncio.iscoroutinefunction(element):
        return None

    try:
        result = element()  # type: ignore[operator]
    except Exception as e:
        LOGGER.debug("mo.lazy: failed to resolve element for export: %s", e)
        return None

    if asyncio.iscoroutine(result):
        result.close()
        return None

    return as_html(result)
