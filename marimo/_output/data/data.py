# Copyright 2023 Marimo. All rights reserved.
import io
import random
import string
from typing import Union

from marimo._runtime.context import get_context
from marimo._runtime.virtual_file import VirtualFile, VirtualFileLifecycleItem


def pdf(
    data: io.IOBase,
) -> VirtualFile:
    """Create a virtual file from a PDF.

    **Args.**
    - data: The data the represents the PDF

    **Returns.**
    A `VirtualFile` object.
    """
    filename = _random_filename("pdf")
    item = VirtualFileLifecycleItem(filename, "application/pdf", data)
    get_context().virtual_file_registry.add(item)
    return item.to_virtual_file()


def image(
    data: io.IOBase,
    ext: string = "png",
) -> VirtualFile:
    """Create a virtual file from an image.

    **Args.**
    - data: The data the represents the image

    **Returns.**
    A `VirtualFile` object.
    """
    filename = _random_filename(ext)
    item = VirtualFileLifecycleItem(filename, f"image/{ext}", data)
    get_context().virtual_file_registry.add(item)
    return item.to_virtual_file()


def _random_filename(ext: string) -> str:
    basename = "".join(random.choices(string.ascii_letters, k=8))
    return f"{basename}.{ext}"
