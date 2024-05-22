# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Coroutine, Final, Union

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.stateless import lazy
from marimo._plugins.ui._core.ui_element import UIElement


@mddoc
class routes(UIElement[str, str]):
    """
    Renders a list of routes that are switched based on the
    URL path.

    Routes currently don't support nested routes, or
    dynamic routes (e.g. `#/user/:id`). If you'd like to
    see these features, please let us know on GitHub:
    https://github.com/marimo-team/marimo/issues

    For a simple-page-application (SPA) experience, you
    should use hash-based routing. For example, prefix
    your routes with `#/`.

    If you are using a multi-page-application (MPA) with
    `marimo.create_asgi_app`, you should use path-based routing.
    For example, prefix your routes with `/`.

    **Examples.**

    ```python
    mo.routes(
        {
            "#/": render_home,
            "#/about": render_about,
            "#/contact": render_contact,
            mo.routes.CATCH_ALL: render_home,
        }
    )
    ```

    **Args.**

    - `routes`: a dictionary of routes, where the key is the URL path
      and the value is a function that returns the content to display.

    **Returns.**

    - An `Html` object.
    """

    _name: Final[str] = "marimo-routes"

    CATCH_ALL = "/(.*)"
    DEFAULT = "/"

    def __init__(
        self,
        routes: dict[
            str,
            Union[
                Callable[[], object],
                Callable[[], Coroutine[None, None, object]],
                object,
            ],
        ],
    ) -> None:
        # For functions, wrap in lazy
        children: list[Html] = []
        for _, content in routes.items():
            if callable(content):
                children.append(lazy.lazy(content))
            else:
                children.append(as_html(content))

        self._children = children
        text = "".join([child.text for child in children])

        super().__init__(
            component_name=self._name,
            initial_value="",
            label=None,
            args={
                "routes": list(routes.keys()),
            },
            on_change=None,
            slotted_html=text,
        )

    def _convert_value(self, value: str) -> str:
        return value

    # Not supported
    def batch(self, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise TypeError(".batch() is not supported on mo.sidebar")

    def center(self, *args: Any, **kwargs: Any) -> Html:
        del args, kwargs
        raise TypeError(".center() is not supported on mo.sidebar")

    def right(self, *args: Any, **kwargs: Any) -> Html:
        del args, kwargs
        raise TypeError(".right() is not supported on mo.sidebar")

    def left(self, *args: Any, **kwargs: Any) -> Html:
        del args, kwargs
        raise TypeError(".left() is not supported on mo.sidebar")

    def callout(self, *args: Any, **kwargs: Any) -> Html:
        del args, kwargs
        raise TypeError(".callout() is not supported on mo.sidebar")

    def style(self, *args: Any, **kwargs: Any) -> Html:
        del args, kwargs
        raise TypeError(".style() is not supported on mo.sidebar")
