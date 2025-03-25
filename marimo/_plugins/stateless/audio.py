# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
import wave
from typing import Optional, Union

import marimo._output.data.data as mo_data
from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.media import io_to_data_url


def convert_numpy_to_wav(data, rate: int, normalize: bool) -> bytes:
    import numpy as np

    def get_normalization_factor(
        max_abs_value, normalize
    ) -> Union[float, int]:
        if not normalize and max_abs_value > 1:
            raise ValueError(
                "Audio data must be between -1 and 1 when normalize=False."
            )
        return max_abs_value if normalize else 1

    data = np.array(data, dtype=float)
    if len(data.shape) == 1:
        nchannels = 1
    elif len(data.shape) == 2:
        nchannels = data.shape[0]
        data = data.T.ravel()
    else:
        raise ValueError("Array audio input must be a 1D or 2D array")

    max_abs_value = np.max(np.abs(data))
    normalization_factor = get_normalization_factor(max_abs_value, normalize)
    scaled = data / normalization_factor * 32767
    scaled = scaled.astype("<h").tobytes()

    buffer = io.BytesIO()
    waveobj = wave.open(buffer, mode="wb")
    waveobj.setnchannels(nchannels)
    waveobj.setframerate(rate)
    waveobj.setsampwidth(2)
    waveobj.setcomptype("NONE", "NONE")
    waveobj.writeframes(scaled)
    val = buffer.getvalue()
    waveobj.close()
    return val


@mddoc
def audio(
    src: Union[str, io.BytesIO],
    rate: int,
    normalize: bool = True,
) -> Html:
    """Render an audio file as HTML.

    Args:
        src: a path or URL to an audio `file`, `bytes`,
            or a file-like object opened in binary mode
            `Numpy 1d array` containing the desired waveform (mono)
            `Numpy 2d array` containing waveforms for each channel.Shape=(NCHAN, NSAMPLES).
        rate :
            The sampling rate of the raw data.
            Only required when data parameter is being used as an array.
        normalize :
            Whether audio should be normalized (rescaled) to the maximum possible
            range. Default is `True`. When set to `False`, `src` must be between
            -1 and 1 (inclusive), otherwise an error is raised.
            Applies only when `src` is a numpy array; other types of
            audio are never normalized.

    Returns:
        An audio player as an `Html` object.

    Example:
        ```python3
        mo.audio(
            src="https://upload.wikimedia.org/wikipedia/commons/8/8c/Ivan_Ili%C4%87-Chopin_-_Prelude_no._1_in_C_major.ogg"
        )

        mo.audio(src="path/to/local/file.wav")
        ```
    """
    resolved_src: Optional[str]
    import numpy as np

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
    elif isinstance(src, np.ndarray):
        if rate is None:
            raise ValueError(
                "rate must be specified when data is a numpy array of audio samples."
            )
        wav_data = convert_numpy_to_wav(src, rate, normalize)
        resolved_src = mo_data.audio(wav_data).url
    else:
        resolved_src = io_to_data_url(src, fallback_mime_type="audio/wav")

    return Html(h.audio(src=resolved_src, controls=True))
