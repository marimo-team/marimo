# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:
    from starlette.responses import Response
    from starlette.types import ASGIApp, Scope


class _HashedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        # Vite emits an eight-character content hash before the extension.
        if response.status_code in (200, 304) and re.search(
            r"-[A-Za-z0-9_-]{8}\.[^.]+$", Path(path).name
        ):
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable"
            )
        return response


def static_assets(directory: Path, *, follow_symlink: bool = False) -> ASGIApp:
    """Serve build assets with compression and immutable hashed URLs.

    Mount only on the build asset directory, never on HTML, user files, or
    streaming endpoints. Unhashed names retain normal conditional caching.
    """
    return GZipMiddleware(
        _HashedStaticFiles(directory=directory, follow_symlink=follow_symlink)
    )
