# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.requests import Request

from marimo import _loggers
from marimo._ast import codegen
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.layout import LayoutConfig, save_layout_config
from marimo._server.model import SessionMode
from marimo._server.models.models import (
    BaseResponse,
    DirectoryAutocompleteRequest,
    DirectoryAutocompleteResponse,
    OpenFileRequest,
    ReadCodeResponse,
    RenameFileRequest,
    SaveAppConfigurationRequest,
    SaveRequest,
    SuccessResponse,
)
from marimo._server.print import print_startup
from marimo._server.router import APIRouter
from marimo._server.utils import canonicalize_filename

LOGGER = _loggers.marimo_logger()

# Router for file endpoints
router = APIRouter()


@router.post("/directory_autocomplete")
@requires("edit")
async def directory_autocomplete(
    *,
    request: Request,
) -> DirectoryAutocompleteResponse:
    """Complete a path to subdirectories and Python files."""
    body = await parse_request(request, cls=DirectoryAutocompleteRequest)
    directory = os.path.dirname(body.prefix)
    if not directory:
        directory = "."

    try:
        subdirectories, files = next(os.walk(directory))[1:]
    except StopIteration:
        return DirectoryAutocompleteResponse(directories=[], files=[])

    basename = os.path.basename(body.prefix)
    directories = sorted([d for d in subdirectories if d.startswith(basename)])
    files = sorted(
        [f for f in files if f.startswith(basename) and f.endswith(".py")]
    )
    return DirectoryAutocompleteResponse(
        directories=directories,
        files=files,
    )


@router.post("/read_code")
@requires("edit")
async def read_code(
    *,
    request: Request,
) -> ReadCodeResponse:
    app_state = AppState(request)
    """Handler for reading code from the server."""
    if app_state.filename is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cannot read code from an unnamed notebook",
        )
    try:
        with open(app_state.filename, "r", encoding="utf-8") as f:
            contents = f.read().strip()
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.SERVER_ERROR,
            detail="Failed to read file: {0}".format(str(e)),
        ) from e

    return ReadCodeResponse(
        contents=contents,
    )


@router.post("/rename")
@requires("edit")
async def rename_file(
    *,
    request: Request,
) -> BaseResponse:
    """Rename the current app."""
    body = await parse_request(request, cls=RenameFileRequest)
    app_state = AppState(request)
    mgr = app_state.session_manager
    filename = body.filename
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


@router.post("/open")
@requires("edit")
async def open_file(
    *,
    request: Request,
) -> BaseResponse:
    """Open a file."""
    app_state = AppState(request)
    body = await parse_request(request, cls=OpenFileRequest)

    # Validate file exists
    if not os.path.exists(body.path):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"File {body.path} does not exist",
        )

    # Get relative path
    filename = os.path.relpath(body.path)

    try:
        app = codegen.get_app(filename)
        if app is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"File {filename} is not a valid marimo app",
            )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}",
        ) from e

    mgr = app_state.session_manager
    mgr.rename(filename)
    host = app_state.host
    port = app_state.port
    run = app_state.mode == SessionMode.RUN
    print_startup(filename=filename, url=f"http://{host}:{port}", run=run)

    return SuccessResponse()


@router.post("/save")
@requires("edit")
async def save(
    *,
    request: Request,
) -> BaseResponse:
    """Save the current app."""
    app_state = AppState(request)
    mgr = app_state.session_manager
    body = await parse_request(request, cls=SaveRequest)
    cell_ids, codes, configs, names, filename, layout = (
        body.cell_ids,
        body.codes,
        body.configs,
        body.names,
        body.filename,
        body.layout,
    )
    filename = canonicalize_filename(filename)
    session = app_state.require_current_session()
    session.app.with_data(
        cell_ids=cell_ids,
        codes=codes,
        names=names,
        configs=configs,
    )

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
            session.app.update_config({"layout_file": layout_filename})
            mgr.update_app_config({"layout_file": layout_filename})

        # try to save the app under the name `filename`
        contents = codegen.generate_filecontents(
            codes,
            names,
            cell_configs=body.configs,
            config=session.app.config,
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


@router.post("/save_app_config")
@requires("edit")
async def save_app_config(
    *,
    request: Request,
) -> BaseResponse:
    """Save the current app."""
    app_state = AppState(request)
    body = await parse_request(request, cls=SaveAppConfigurationRequest)
    mgr = app_state.session_manager

    # Update the file with the latest app config
    # TODO(akshayka): Only change the `app = marimo.App` line (at top level
    # of file), instead of overwriting the whole file.
    app = app_state.require_current_session().app

    new_config = app.update_config(body.config)
    mgr.update_app_config(body.config)

    if mgr.filename is not None:
        # Try to save the app under the name `mgr.filename`
        contents = codegen.generate_filecontents(
            codes=list(app.cell_manager.codes()),
            names=list(app.cell_manager.names()),
            cell_configs=list(app.cell_manager.configs()),
            config=new_config,
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
