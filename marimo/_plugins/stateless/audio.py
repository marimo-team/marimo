# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
from typing import Union

from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc


@mddoc
def audio(
    src: Union[str, io.IOBase],
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
    resolved_src = src if isinstance(src, str) else _io_to_data_url(src)
    audio = h.audio(src=resolved_src, controls=True)
    return Html(audio)


def _io_to_data_url(readable: io.IOBase) -> str:
    base64_string = base64.b64encode(readable.read()).decode("utf-8")
    file_type = _guess_mime_type(readable)
    return f"data:{file_type};base64,{base64_string}"


def _guess_mime_type(src: Union[str, io.IOBase]) -> str:
    file_name: str
    if isinstance(src, str):
        file_name = src
    elif isinstance(src, io.FileIO):
        src_name = src.name
        if isinstance(src_name, str):
            file_name = src_name
        else:
            # If we can't guess the file type, default to audio/wav
            return "audio/wav"
    else:
        return "audio/wav"

    file_type = file_name.split(".")[-1]
    if file_type in INCONSISTENT_AUDIO_MIME_TYPES:
        return f"audio/{INCONSISTENT_AUDIO_MIME_TYPES[file_type]}"
    return f"audio/{file_type}"


# Reference here:
# https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
INCONSISTENT_AUDIO_MIME_TYPES = {
    "mp3": "mpeg",
    "oga": "ogg",
    "mid": "midi",
    "weba": "webm",
}
