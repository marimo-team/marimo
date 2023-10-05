# Copyright 2023 Marimo. All rights reserved.
import random
import string
import threading

from marimo._runtime.context import get_context
from marimo._runtime.virtual_file import VirtualFile, VirtualFileLifecycleItem


def pdf(
    data: bytes,
) -> VirtualFile:
    """Create a virtual file from a PDF.

    **Args.**

    - data: PDF data in bytes

    **Returns.**

    A `VirtualFile` object.
    """
    filename = _random_filename("pdf")
    item = VirtualFileLifecycleItem(filename, data)
    get_context().cell_lifecycle_registry.add(item)
    return item.virtual_file


def image(
    data: bytes,
    ext: str = "png",
) -> VirtualFile:
    """Create a virtual file from an image.

    **Args.**

    - data: Image data in bytes

    **Returns.**

    A `VirtualFile` object.
    """
    filename = _random_filename(ext)
    item = VirtualFileLifecycleItem(filename, data)
    get_context().cell_lifecycle_registry.add(item)
    return item.virtual_file


_ALPHABET = string.ascii_letters + string.digits


def _random_filename(ext: str) -> str:
    # adapted from: https://stackoverflow.com/questions/13484726/safe-enough-8-character-short-unique-random-string  # noqa: E501
    # TODO(akshayka): should callers redraw if they get a collision?
    tid = str(threading.get_native_id())
    basename = tid + "-" + "".join(random.choices(_ALPHABET, k=8))
    return f"{basename}.{ext}"
