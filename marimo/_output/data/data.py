# Copyright 2023 Marimo. All rights reserved.
import string
import uuid

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
    basename = str(uuid.uuid4())
    return f"{basename}.{ext}"
