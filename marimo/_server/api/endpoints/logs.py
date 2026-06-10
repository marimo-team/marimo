# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.responses import JSONResponse, PlainTextResponse

from marimo._loggers import get_log_directory
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.requests import Request

router = APIRouter()

MAX_LINES = 500


def list_log_files_in_directory(log_dir: Path) -> list[str]:
    """Return sorted list of .log filenames in the given directory."""
    if not log_dir.exists():
        return []
    files = [
        f.name
        for f in log_dir.iterdir()
        # Only include .log files; rotated backups like
        # marimo.log.2026-02-13 have a different suffix
        if f.is_file() and f.suffix == ".log"
    ]
    files.sort()
    return files


def read_log_file(log_dir: Path, filename: str) -> tuple[str | None, int]:
    """Read the tail of a log file.

    Returns (content, status_code). If content is None, it's an error message.
    """
    # Validate filename to prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return ("Invalid filename", 400)

    file_path = log_dir / filename

    # Ensure the resolved path is within the log directory
    try:
        file_path.resolve().relative_to(log_dir.resolve())
    except ValueError:
        return ("Invalid filename", 400)

    if not file_path.exists() or not file_path.is_file():
        return ("File not found", 404)

    try:
        text = file_path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        tail = lines[-MAX_LINES:]
        return ("".join(tail), 200)
    except Exception:
        return ("Failed to read file", 500)


@router.get("/list")
@requires("edit")
async def list_log_files(request: Request) -> JSONResponse:
    """
    responses:
        200:
            description: List available log files
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            files:
                                type: array
                                items:
                                    type: string
    """
    del request  # Unused
    files = list_log_files_in_directory(get_log_directory())
    return JSONResponse({"files": files})


@router.get("/{filename}")
@requires("edit")
async def get_log_file(request: Request) -> PlainTextResponse:
    """
    responses:
        200:
            description: Tail a log file
            content:
                text/plain:
                    schema:
                        type: string
        400:
            description: Invalid filename
        404:
            description: File not found
    """
    filename = request.path_params["filename"]
    content, status_code = read_log_file(get_log_directory(), filename)
    return PlainTextResponse(content, status_code=status_code)
