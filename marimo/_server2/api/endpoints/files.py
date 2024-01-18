# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.cell import CellConfig
from marimo._server.api.status import HTTPStatus
from marimo._server.layout import LayoutConfig, save_layout_config
from marimo._server.utils import canonicalize_filename
from marimo._server2.api.deps import (
    SessionManagerDep,
    SessionManagerStateDep,
)
from marimo._server2.models.models import (
    BaseResponse,
    DirectoryAutocompleteRequest,
    DirectoryAutocompleteResponse,
    ReadCodeResponse,
    RenameFileRequest,
    SaveAppConfigurationRequest,
    SaveRequest,
    SuccessResponse,
)

LOGGER = _loggers.marimo_logger()

# Router for file endpoints
router = APIRouter()


@router.post(
    "/directory_autocomplete", response_model=DirectoryAutocompleteResponse
)
def directory_autocomplete(
    *,
    request: DirectoryAutocompleteRequest,
) -> DirectoryAutocompleteResponse:
    """Complete a path to subdirectories and Python files."""

    directory = os.path.dirname(request.prefix)
    if not directory:
        directory = "."

    try:
        subdirectories, files = next(os.walk(directory))[1:]
    except StopIteration:
        return DirectoryAutocompleteResponse(directories=[], files=[])

    basename = os.path.basename(request.prefix)
    directories = sorted([d for d in subdirectories if d.startswith(basename)])
    files = sorted(
        [f for f in files if f.startswith(basename) and f.endswith(".py")]
    )
    return DirectoryAutocompleteResponse(
        directories=directories,
        files=files,
    )


@router.post("/read_code", response_model=ReadCodeResponse)
def read_code(
    *,
    state: SessionManagerStateDep,
) -> ReadCodeResponse:
    """Handler for reading code from the server."""
    if state.filename is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cannot read code from an unnamed notebook",
        )
    try:
        with open(state.filename, "r", encoding="utf-8") as f:
            contents = f.read().strip()
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.SERVER_ERROR,
            detail="Failed to read file: {0}".format(str(e)),
        ) from e

    return ReadCodeResponse(
        contents=contents,
    )


@router.post("/rename", response_model=BaseResponse)
def rename_file(
    *,
    request: RenameFileRequest,
    mgr: SessionManagerDep,
) -> BaseResponse:
    """Rename the current app."""
    filename = request.filename
    LOGGER.debug("Renaming from %s to %s", mgr.filename, filename)
    filename = canonicalize_filename(filename)

    if filename == mgr.filename:
        # no-op
        pass
    elif os.path.exists(filename):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File {0} already exists".format(filename),
        )
    elif mgr.filename is None:
        try:
            # create a file named `filename`
            with open(filename, "w") as _:
                pass
        except Exception as err:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail="Failed to create file {0}".format(filename),
            ) from err
        mgr.rename(filename)
    else:
        try:
            os.rename(mgr.filename, filename)
        except Exception as err:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail="Failed to rename from {0} to {1}".format(
                    mgr.filename, filename
                ),
            ) from err
        mgr.rename(filename)

    return SuccessResponse()


@router.post("/save", response_model=BaseResponse)
def save(
    *,
    request: SaveRequest,
    mgr: SessionManagerDep,
) -> BaseResponse:
    """Save the current app."""
    codes, names, filename, layout = (
        request.codes,
        request.names,
        request.filename,
        request.layout,
    )
    filename = canonicalize_filename(filename)
    if mgr.filename is not None and mgr.filename != filename:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Save handler cannot rename files.",
        )
    elif mgr.filename is None and os.path.exists(filename):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File {0} already exists".format(filename),
        )
    else:
        # save layout
        if layout is not None:
            app_dir = os.path.dirname(filename)
            app_name = os.path.basename(filename)
            layout_filename = save_layout_config(
                app_dir, app_name, LayoutConfig(**layout)
            )
            mgr.update_app_config({"layout_file": layout_filename})

        # try to save the app under the name `filename`
        contents = codegen.generate_filecontents(
            codes,
            names,
            cell_configs=[
                CellConfig(**config.dict()) for config in request.configs
            ],
            config=mgr.app_config,
        )
        LOGGER.debug("Saving app to %s", filename)
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(contents)
        except Exception as e:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail="Failed to save file: {0}".format(str(e)),
            ) from e
        if mgr.filename is None:
            mgr.rename(filename)

    return SuccessResponse()


@router.post("/save_app_config", response_model=BaseResponse)
def save_app_config(
    *,
    request: SaveAppConfigurationRequest,
    mgr: SessionManagerDep,
) -> BaseResponse:
    """Save the current app."""
    mgr.update_app_config(request.config)
    # Update the file with the latest app config
    # TODO(akshayka): Only change the `app = marimo.App` line (at top level
    # of file), instead of overwriting the whole file.
    app = mgr.load_app()
    if app is not None and mgr.filename is not None:
        codes = list(app._codes())
        names = list(app._names())
        configs = list(app._configs())

        # Try to save the app under the name `mgr.filename`
        contents = codegen.generate_filecontents(
            codes, names, cell_configs=configs, config=mgr.app_config
        )
        try:
            with open(mgr.filename, "w", encoding="utf-8") as f:
                f.write(contents)
        except Exception as e:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail="Failed to save file: {0}".format(str(e)),
            ) from e

    return SuccessResponse()
