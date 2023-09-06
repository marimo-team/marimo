# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import Union

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

    with open("recording.wav", "rb") as file:
        mo.audio(src=file)
    ```

    **Args.**

    - `src`: the URL of the audio or a file-like object

    **Returns.**

    An audio player as an `Html` object.
    """
    resolved_src = io_to_data_url(src, fallback_mime_type="audio/wav")
    audio = h.audio(src=resolved_src, controls=True)
    return Html(audio)
