# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable, Coroutine, Union

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._plugins.stateless import lazy


@mddoc
def routes(
    routes: dict[
        str,
        Union[
            Callable[[], object],
            Callable[[], Coroutine[None, None, object]],
            object,
        ],
    ],
) -> Html:
    """
    Renders a list of routes that are switched based on the
    URL path.

    Routes currently don't support nested routes, or
    dynamic routes (e.g. `#/user/:id`). If you'd like to
    see these features, please let us know on GitHub:
    https://github.com/marimo-team/marimo/issues

    For a simple-page-application (SPA) experience, use
    should use hash-based routing. For example, prefix
    your routes with `#/`.

    If you are using a multi-page-application (MPA) with
    `marimo.create_asgi_app`, you should use path-based routing.
    For example, prefix your routes with `/`.

    **Examples.**

    ```python
    mo.routes(
        {
            "#/home": render_home(),  # not lazily evaluated
            "#/about": render_about,
            "#/contact": render_contact,
        }
    )
    ```

    **Args.**

    - `routes`: a dictionary of routes, where the key is the URL path
      and the value is a function that returns the content to display.

    **Returns.**

    - An `Html` object.
    """

    # For functions, wrap in lazy
    children: list[str] = []
    for _, content in routes.items():
        if callable(content):
            children.append(lazy.lazy(content).text)
        else:
            children.append(as_html(content).text)

    return Html(
        build_stateless_plugin(
            "marimo-routes",
            {
                "routes": list(routes.keys()),
            },
            "".join(children),
        )
    )
