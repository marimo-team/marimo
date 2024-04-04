import io
import marimo as mo

from typing import Callable, Any
import PIL.Image


class Output:
    def __init__(self, value: object, html: mo.Html | None = None) -> None:
        self.value = value
        self.html = html

    def _mime_(self) -> tuple[str, str]:
        return (
            "text/html",
            self.html.text
            if self.html is not None
            else mo.as_html(self.value).text,
        )


def default_output(data: bytes) -> Output:
    return Output(value=data)


def construct_output_function(
    inference_function: Callable[..., object],
    output: Callable[[Any], Output] = default_output,
):
    return lambda *args: output(inference_function(*args))


def image_output(value: PIL.Image.Image) -> Output:
    stream = io.BytesIO()
    value.save(stream, format="PNG")
    return Output(value, html=mo.image(stream))


def audio_output_from_path(value: str) -> Output:
    with open(value, "rb") as f:
        audio = mo.audio(io.BytesIO(f.read()))

    return Output(value=value, html=audio)


def audio_output_from_bytes(value: bytes) -> Output:
    audio = mo.audio(io.BytesIO(value))
    return Output(value=value, html=audio)
