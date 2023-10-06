# Copyright 2023 Marimo. All rights reserved.
from marimo._runtime.context import get_context
from marimo._runtime.virtual_file import VirtualFile, VirtualFileLifecycleItem


def pdf(data: bytes) -> VirtualFile:
    """Create a virtual file from a PDF.

    **Args.**

    - data: PDF data in bytes

    **Returns.**

    A `VirtualFile` object.
    """
    item = VirtualFileLifecycleItem(ext="pdf", buffer=data)
    get_context().cell_lifecycle_registry.add(item)
    return item.virtual_file


def image(data: bytes, ext: str = "png") -> VirtualFile:
    """Create a virtual file from an image.

    **Args.**

    - data: Image data in bytes

    **Returns.**

    A `VirtualFile` object.
    """
    item = VirtualFileLifecycleItem(ext=ext, buffer=data)
    get_context().cell_lifecycle_registry.add(item)
    return item.virtual_file
