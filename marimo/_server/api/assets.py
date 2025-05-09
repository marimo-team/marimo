from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Union

from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, Response

from marimo import _loggers
from marimo._utils import requests
from marimo._utils.url import is_url

LOGGER = _loggers.marimo_logger()

URLOrPath = Union[str, Path]


class StaticAssetsHandler:
    def __init__(self, root: URLOrPath) -> None:
        self._root = root
        self._is_url: bool = is_url(str(root)) if root else False

    @property
    def root(self) -> URLOrPath:
        return self._root

    @property
    def path(self) -> Path:
        return Path(self._root)

    @property
    def is_url(self) -> bool:
        return self._is_url

    @property
    def is_file(self) -> bool:
        return not self.is_url

    def is_symlink(self) -> bool:
        if not self.is_file:
            return False
        path = self.path
        assets_dir = path / "assets"
        return path.is_symlink() and assets_dir.is_symlink()

    async def get(self, path: str) -> Response:
        """Get a file from the static assets directory."""
        if self.is_url:
            return await self._get_file_from_url(path)
        elif self.is_file:
            return await self._get_file_from_file(path)
        else:
            raise HTTPException(
                status_code=500, detail="Static assets not configured"
            )

    def read(self, path: str) -> str:
        """Read a file from the static assets directory."""
        if self.is_url:
            return requests.get(self.join_url(path)).text()
        elif self.is_file:
            return (self.path / path).read_text()
        else:
            raise HTTPException(
                status_code=500, detail="Static assets not configured"
            )

    async def _get_file_from_url(self, path: str) -> Response:
        url = self.join_url(path)
        LOGGER.warning(f"Fetching {url}")
        response = requests.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="File not found")

        def get_media_type(url: str) -> str:
            media_type = response.headers.get("content-type", None)
            if media_type:
                return media_type
            guessed_media_type = mimetypes.guess_type(url)[0]
            return guessed_media_type or "application/octet-stream"

        return Response(
            content=response.content,
            media_type=get_media_type(url),
        )

    def join_url(self, path: str) -> str:
        # Avoid issues with double slashes
        return f"{str(self.root).rstrip('/')}/{path.lstrip('/')}"

    async def _get_file_from_file(self, path: str) -> Response:
        file_path = self.path / path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(file_path)
