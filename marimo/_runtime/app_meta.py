# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._config.config import DEFAULT_CONFIG
from marimo._output.rich_help import mddoc
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)
from marimo._runtime.context.utils import RunMode, get_mode
from marimo._runtime.requests import HTTPRequest


@mddoc
class AppMeta:
    """Metadata about the app.

    This class provides access to runtime metadata about a marimo app, such as
    its display theme and execution mode.
    """

    @property
    def theme(self) -> str:
        """The display theme of the app.

        Returns:
            str: Either "light" or "dark". If the user's configuration is set to
                "system", currently returns "light".

        Examples:
            Get the current theme and conditionally set a plotting library's theme:

            ```python
            import altair as alt

            # Enable dark theme for Altair when marimo is in dark mode
            alt.themes.enable(
                "dark" if mo.app_meta().theme == "dark" else "default"
            )
            ```
        """
        try:
            context = get_context()
            marimo_config = context.marimo_config
        except ContextNotInitializedError:
            marimo_config = DEFAULT_CONFIG

        theme = marimo_config["display"]["theme"] or "light"
        if theme == "system":
            # TODO(mscolnick): have frontend tell the backend the system theme
            return "light"
        return theme

    @property
    def mode(self) -> Optional[RunMode]:
        """
        The execution mode of the app.

        Examples:
            Show content only in edit mode:

            ```python
            # Only show this content when editing the notebook
            mo.md(
                "# Developer Notes"
            ) if mo.app_meta().mode == "edit" else None
            ```

        Returns:
            - "edit": The notebook is being edited in the marimo editor
            - "run": The notebook is being run as an app
            - "script": The notebook is being run as a script
            - "test": The cell has been invoked by a test
            - None: The mode could not be determined
        """
        return get_mode()

    @property
    def request(self) -> Optional[HTTPRequest]:
        """
        The current HTTP request if any. The shape of the request object depends on the ASGI framework used,
        but typically includes:

        - `headers`: Request headers
        - `cookies`: Request cookies
        - `query_params`: Query parameters
        - `path_params`: Path parameters
        - `user`: User data added by authentication middleware
        - `url`: URL information including path, query parameters

        Examples:
            Get the current request and print the path:

            ```python
            request = mo.app_meta().request
            user = request.user
            print(
                user["is_authenticated"], user["username"], request.url["path"]
            )
            ```

        Returns:
            Optional[HTTPRequest]: The current request object if available, None otherwise.
        """
        try:
            context = get_context()
            return context.request
        except ContextNotInitializedError:
            return None
