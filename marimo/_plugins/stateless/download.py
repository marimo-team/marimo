# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import Optional, Union

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.media import (
    guess_mime_type,
    io_to_data_url,
    is_data_empty,
)
from marimo._plugins.core.web_component import build_stateless_plugin


@mddoc
def download(
    data: Union[str, bytes, io.BytesIO],
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

    - `data`: The data to download. Can be a string, bytes,
        or a file-like object.
    - `filename`: The name of the file to download.
        If not provided, the name will be guessed from the data.
    - `mimetype`: The mimetype of the file to download, for example,
        (e.g. "text/csv", "image/png"). If not provided,
        the mimetype will be guessed from the filename.

    **Returns.**

    An `Html` object for a download button.
    """
    # name used to guess mimetype
    name_for_mime = data if isinstance(data, str) else filename
    resolved_mimetype = (
        mimetype or guess_mime_type(name_for_mime) or "text/plain"
    )
    disabled = disabled or is_data_empty(data)

    # TODO: for large files or external URLs, we should create a
    # temporary file URL at /api/kernel/download/<resource_id> that
    # the frontend can use to download the file. This will
    # lazily read the file and avoid loading it into memory.

    return Html(
        build_stateless_plugin(
            component_name="marimo-download",
            args={
                "data": io_to_data_url(
                    data, fallback_mime_type=resolved_mimetype
                ),
                "filename": filename,
                "disabled": disabled,
                "label": label,
            },
        )
    )
