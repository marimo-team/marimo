# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
from typing import Optional, Union

import marimo._output.data.data as mo_data
from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.media import io_to_data_url


@mddoc
def audio(
    src: Union[str, io.BytesIO],
) -> Html:
    """Render an audio file as HTML.

    **Example.**

    ```python3
    mo.audio(
        src="https://upload.wikimedia.org/wikipedia/commons/8/8c/Ivan_Ili%C4%87-Chopin_-_Prelude_no._1_in_C_major.ogg"
    )

    mo.audio(src="path/to/local/file.wav")
    ```

    **Args.**

    - `src`: a path or URL to an audio file, bytes,
        or a file-like object opened in binary mode

    **Returns.**

    An audio player as an `Html` object.
    """
    resolved_src: Optional[str]

    if isinstance(src, (io.BufferedReader, io.BytesIO)):
        pos = src.tell()
        src.seek(0)
        resolved_src = mo_data.audio(src.read()).url
        src.seek(pos)
    elif isinstance(src, bytes):
        resolved_src = mo_data.audio(src).url
    elif isinstance(src, str) and os.path.isfile(os.path.expanduser(src)):
        src = os.path.expanduser(src)
        with open(src, "rb") as f:
            resolved_src = mo_data.audio(
                f.read(), ext=os.path.splitext(src)[1]
            ).url
    else:
        resolved_src = io_to_data_url(src, fallback_mime_type="audio/wav")

    return Html(h.audio(src=resolved_src, controls=True))
