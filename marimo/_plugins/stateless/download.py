# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import Optional, Union

import marimo._output.data.data as mo_data
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.media import (
    guess_mime_type,
    is_data_empty,
    mime_type_to_ext,
)
from marimo._plugins.core.web_component import build_stateless_plugin


@mddoc
def download(
    data: Union[str, bytes, io.BytesIO, io.BufferedReader],
    filename: Optional[str] = None,
    mimetype: Optional[str] = None,
    disabled: bool = False,
    *,
    label: str = "Download",
) -> Html:
    """
    Show a download button for a url, bytes, or file-like object.

    **Examples.**

    ```python
    download_txt = mo.download(
        data="Hello, world!".encode("utf-8"),
        filename="hello.txt",
        mimetype="text/plain",
    )

    download_image = mo.download(
        data=open("hello.png", "rb"),
    )
    ```

    **Args.**

    - `data`: The data to download. Can be a string (interpreted as
        a URL), bytes, or a file opened in binary mode.
    - `filename`: The name of the file to download.
        If not provided, the name will be guessed from the data.
    - `mimetype`: The mimetype of the file to download, for example,
        (e.g. "text/csv", "image/png"). If not provided,
        the mimetype will be guessed from the filename.

    **Returns.**

    An `Html` object for a download button.
    """

    # Convert to bytes right away since can only be read once
    if isinstance(data, io.BufferedReader):
        filename = filename or data.name
        data.seek(0)
        data = data.read()

    # name used to guess mimetype
    name_for_mime = data if isinstance(data, str) else filename
    resolved_mimetype = (
        mimetype or guess_mime_type(name_for_mime) or "text/plain"
    )
    ext = mime_type_to_ext(resolved_mimetype) or "txt"
    disabled = disabled or is_data_empty(data)

    # create a virtual file to avoid loading the data in the browser
    file = mo_data.any_data(data, ext=ext)

    return Html(
        build_stateless_plugin(
            component_name="marimo-download",
            args={
                "data": file.url,
                "filename": filename,
                "disabled": disabled,
                "label": label,
            },
        )
    )
