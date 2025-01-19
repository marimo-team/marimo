# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Final, Optional, Union, cast

import marimo._output.data.data as mo_data
from marimo._output.rich_help import mddoc
from marimo._plugins.core.media import (
    guess_mime_type,
    io_to_data_url,
    is_data_empty,
    mime_type_to_ext,
)
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.functions import EmptyArgs, Function

DataType = Union[str, bytes, io.BytesIO, io.BufferedReader]


@dataclass
class LoadResponse:
    data: str
    filename: Optional[str]


@mddoc
class download(UIElement[None, None]):
    """
    Show a download button for a url, bytes, or file-like object.

    Args:
        data (Union[str, bytes, io.BytesIO, callable]): The data to download. Can be:
            - string (interpreted as a URL)
            - bytes
            - file opened in binary mode
            - callable returning any of the above (for lazy loading)
            - async callable returning any of the above (for lazy loading)
        filename (str): The name of the file to download.
            If not provided, the name will be guessed from the data.
        mimetype (str): The mimetype of the file to download, for example,
            (e.g. "text/csv", "image/png"). If not provided,
            the mimetype will be guessed from the filename.
        disabled (bool): Whether to disable the download button.
        label (str): The label of the download button.

    Example:
        ```python
        # Eager loading
        download_txt = mo.download(
            data="Hello, world!".encode("utf-8"),
            filename="hello.txt",
            mimetype="text/plain",
        )


        # Lazy loading
        def get_large_data():
            return b"large data"


        download_lazy = mo.download(
            data=get_large_data,
            filename="large.txt",
        )
        ```
    """

    _name: Final[str] = "marimo-download"

    def __init__(
        self,
        data: Union[
            DataType,
            Callable[[], DataType],
            Callable[[], Coroutine[None, None, DataType]],
        ],
        filename: Optional[str] = None,
        mimetype: Optional[str] = None,
        disabled: bool = False,
        *,
        label: str = "Download",
    ) -> None:
        self._data = data
        self._filename = filename
        self._mimetype = mimetype

        data_url = ""
        is_lazy = callable(data)

        # name used to guess mimetype
        name_for_mime = data if isinstance(data, str) else filename
        resolved_mimetype = (
            mimetype or guess_mime_type(name_for_mime) or "text/plain"
        )
        ext = mime_type_to_ext(resolved_mimetype) or "txt"

        # Convert to bytes right away since can only be read once
        if isinstance(data, io.BufferedReader):
            filename = filename or data.name
            data.seek(0)
            data = data.read()

        # When non-lazy
        if not callable(data):
            # Maybe update disabled
            disabled = disabled or is_data_empty(data)

            # Maybe update name
            if filename is None and hasattr(data, "name"):
                filename = cast(str, cast(Any, data).name)

            # create a virtual file to avoid loading the data in the browser
            # only if the data is not lazy
            data_url = mo_data.any_data(data, ext=ext).url

        super().__init__(
            component_name=self._name,
            initial_value=None,
            label=label,
            on_change=None,
            args={
                "data": data_url,
                "filename": filename,
                "disabled": disabled,
                "lazy": is_lazy,
            },
            functions=(
                (
                    Function(
                        name="load",
                        arg_cls=EmptyArgs,
                        function=self._load,
                    ),
                )
            ),
        )

    async def _load(self, _args: EmptyArgs) -> LoadResponse:
        if callable(self._data) and not isinstance(self._data, UIElement):
            result_or_coroutine = self._data()
            if asyncio.iscoroutine(result_or_coroutine):
                result = await result_or_coroutine
            else:
                result = result_or_coroutine
        else:
            result = self._data

        url = io_to_data_url(
            result, fallback_mime_type=self._mimetype or "text/plain"
        )

        if url is None:
            raise ValueError("Failed to convert data to data URL")

        return LoadResponse(data=url, filename=self._filename)

    def _convert_value(self, value: None) -> None:
        return value
