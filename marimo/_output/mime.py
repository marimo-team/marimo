# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from marimo._messaging.mimetypes import KnownMimeType


@dataclass
class MIME(Protocol):
    """Protocol for instantiating objects using marimo's media viewer.

    To implement this protocol, a class needs to define
    just one method, _mime_.
    """

    # TODO(akshayka): Single source of truth for supported mimetypes. The
    # documented types below are copied from the frontend
    def _mime_(self) -> tuple[KnownMimeType, str]:
        """Return a tuple (mimetype, data)

        Return a mimetype and the string data to instantiate it in marimo's
        media viewer.

        The supported mimetypes are:
          application/json
          application/vnd.marimo+error
          application/vnd.marimo+traceback
          image/png
          image/svg+xml
          image/tiff
          image/avif
          image/bmp
          image/gif
          image/jpeg
          video/mp4
          video/mpeg
          text/html
          text/plain
        """
        raise NotImplementedError
