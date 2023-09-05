# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import base64
import io
from typing import Final

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement


@mddoc
class microphone(UIElement[str, io.BytesIO]):
    """An audio recorder element.

    Use `mo.microphone` to record audio via the user's browser. The
    user must grant permission to use the microphone.

    **Example.**

    ```python
    mic = mo.ui.microphone()
    mic
    ```

    ```python
    mo.audio(mic.value)
    ```

    **Attributes.**

    - `value`: The blob of the recorded audio, as an `io.BytesIO` object.

    **Initialization Args.**

    - `label`: optional text label for the element
    """

    name: Final[str] = "marimo-microphone"

    def __init__(
        self,
        *,
        label: str = "",
    ) -> None:
        super().__init__(
            component_name=microphone.name,
            initial_value="",
            label=label,
            args={},
        )

    def _convert_value(self, value: str) -> io.BytesIO:
        return io.BytesIO(base64.b64decode(value))
