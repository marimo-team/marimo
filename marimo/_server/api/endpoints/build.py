# Copyright 2026 Marimo. All rights reserved.
"""HTTP endpoints for the in-editor Build panel.

Three operations:

- ``POST /preview`` — synchronous; returns a per-cell prediction of the
  compiled-notebook outcome, computed from the saved file's AST plus
  whatever live values the kernel has bound (best effort).
- ``POST /run`` — schedules :func:`marimo._build.build_notebook` on a
  background thread and returns immediately. Per-cell + phase progress
  is streamed to the frontend via the existing kernel→frontend
  WebSocket as :class:`marimo._messaging.notification.BuildEventNotification`
  ops, tagged with the ``build_id`` returned here.
- ``POST /cancel`` — sets the in-flight build's cancel flag; the
  runner observes it between cells and raises :class:`BuildCancelled`,
  surfaced to the UI as a ``cancelled`` event.

The build runs in the **server** process (not the kernel), so it
never blocks the kernel's event loop and isn't affected by the user's
running cells. A build re-parses the source file from disk via
:func:`marimo._ast.load.load_app`, so the user must save first; the
frontend handles that.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import msgspec
from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._ast.app import InternalApp
from marimo._build import build_notebook
from marimo._build.events import BuildProgressEvent
from marimo._build.preview import compute_preview
from marimo._build.runner import BuildCancelled, BuildExecutionError
from marimo._messaging.msgspec_encoder import asdict as ms_asdict
from marimo._messaging.notification import BuildEventNotification
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import BaseResponse
from marimo._server.router import APIRouter
from marimo._utils.http import HTTPStatus

if TYPE_CHECKING:
    from starlette.requests import Request


LOGGER = _loggers.marimo_logger()
router = APIRouter()

# One worker is plenty: builds are CPU/IO heavy and one-at-a-time per
# session. Daemon=True so a hung build doesn't block process shutdown.
_BUILD_EXECUTOR = ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="marimo-build"
)


@dataclass
class _BuildHandle:
    """Per-session record of one in-flight (or recently finished) build."""

    build_id: str
    cancel_event: threading.Event
    state: str = "running"  # running | success | error | cancelled


# Session id → currently-tracked build. We allow at most one build per
# session at a time; a second ``/run`` while one is in flight returns
# 409. The handle stays around after completion so a late ``/cancel``
# is a no-op rather than a crash.
_BUILDS: dict[str, _BuildHandle] = {}
_BUILDS_LOCK = threading.Lock()


# --- Request / response shapes ----------------------------------------------


class BuildPreviewRequest(msgspec.Struct, rename="camel"):
    """No body needed today; struct kept for future fields (e.g. dry_run)."""


class BuildPreviewCellResponse(msgspec.Struct, rename="camel"):
    cell_id: str
    name: str
    display_name: str
    predicted_kind: str | None
    confidence: str


class BuildPreviewResponse(BaseResponse):
    success: bool = True
    cells: list[BuildPreviewCellResponse] = msgspec.field(default_factory=list)


class BuildRunRequest(msgspec.Struct, rename="camel"):
    force: bool = False
    output_dir: str | None = None


class BuildRunResponse(BaseResponse):
    success: bool = True
    build_id: str = ""


class BuildCancelRequest(msgspec.Struct, rename="camel"):
    build_id: str


# --- Endpoints --------------------------------------------------------------


@router.post("/preview")
@requires("edit")
async def preview(*, request: Request) -> JSONResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/BuildPreviewRequest"
    responses:
        200:
            description: Predict each cell's outcome in the compiled notebook.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/BuildPreviewResponse"
    """
    app_state = AppState(request)
    session = app_state.require_current_session()
    # Body is optional; ignore parse failures so the panel can poll
    # with a literal empty body.
    try:
        await parse_request(request, cls=BuildPreviewRequest)
    except Exception:
        pass

    internal: InternalApp = session.app_file_manager.app
    plan = compute_preview(
        graph=internal.graph,
        cell_manager=internal.cell_manager,
    )
    return JSONResponse(
        content=ms_asdict(
            BuildPreviewResponse(
                cells=[
                    BuildPreviewCellResponse(
                        cell_id=str(c.cell_id),
                        name=c.name,
                        display_name=c.display_name,
                        predicted_kind=(
                            c.predicted_kind.value
                            if c.predicted_kind is not None
                            else None
                        ),
                        confidence=c.confidence,
                    )
                    for c in plan.cells
                ]
            )
        )
    )


@router.post("/run")
@requires("edit")
async def run(*, request: Request) -> JSONResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/BuildRunRequest"
    responses:
        200:
            description: Schedule a build; progress streams via WebSocket BuildEvent ops.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/BuildRunResponse"
        400:
            description: Notebook must be saved before building.
        409:
            description: A build is already in flight for this session.
    """
    app_state = AppState(request)
    session = app_state.require_current_session()
    session_id = app_state.require_current_session_id()
    body = await parse_request(request, cls=BuildRunRequest)

    if not session.app_file_manager.is_notebook_named:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Save the notebook before building.",
        )
    notebook_path = session.app_file_manager.path
    if notebook_path is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Notebook has no path on disk.",
        )

    with _BUILDS_LOCK:
        existing = _BUILDS.get(session_id)
        if existing is not None and existing.state == "running":
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=(
                    "A build is already in flight for this session "
                    f"({existing.build_id}); cancel it first."
                ),
            )
        build_id = uuid.uuid4().hex
        handle = _BuildHandle(
            build_id=build_id,
            cancel_event=threading.Event(),
        )
        _BUILDS[session_id] = handle

    output_dir = Path(body.output_dir) if body.output_dir else None

    def _progress(event: BuildProgressEvent) -> None:
        # Wire this synchronously from the runner thread. The session's
        # asyncio.Queue is fed via ``put_nowait``, which we rely on here
        # for the same reason the file-watcher does.
        try:
            session.notify(
                BuildEventNotification(
                    build_id=build_id,
                    event_type=getattr(event, "type", "unknown"),
                    payload=_event_payload(event),
                ),
                from_consumer_id=None,
            )
        except Exception:
            LOGGER.exception("Failed to forward build event")

    def _run_in_thread() -> None:
        try:
            build_notebook(
                notebook_path,
                output_dir=output_dir,
                force=body.force,
                progress_callback=_progress,
                should_cancel=handle.cancel_event.is_set,
            )
            handle.state = "success"
        except BuildCancelled:
            handle.state = "cancelled"
        except BuildExecutionError as e:
            handle.state = "error"
            session.notify(
                BuildEventNotification(
                    build_id=build_id,
                    event_type="error",
                    payload={
                        "message": str(e),
                        "cell_name": e.cell_name,
                    },
                ),
                from_consumer_id=None,
            )
        except Exception as e:
            # A terminal ``error`` event was already emitted by
            # build_notebook's outer try; the state assignment here
            # just marks the handle as a non-running tombstone.
            LOGGER.exception("Build crashed")
            handle.state = "error"
            session.notify(
                BuildEventNotification(
                    build_id=build_id,
                    event_type="error",
                    payload={"message": str(e), "cell_name": None},
                ),
                from_consumer_id=None,
            )

    _BUILD_EXECUTOR.submit(_run_in_thread)
    return JSONResponse(
        content=ms_asdict(BuildRunResponse(success=True, build_id=build_id))
    )


@router.post("/cancel")
@requires("edit")
async def cancel(*, request: Request) -> JSONResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/BuildCancelRequest"
    responses:
        200:
            description: Cancel an in-flight build (idempotent).
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/BaseResponse"
    """
    app_state = AppState(request)
    session_id = app_state.require_current_session_id()
    body = await parse_request(request, cls=BuildCancelRequest)

    with _BUILDS_LOCK:
        handle = _BUILDS.get(session_id)
    if handle is None or handle.build_id != body.build_id:
        return JSONResponse(content=ms_asdict(BaseResponse(success=False)))
    handle.cancel_event.set()
    return JSONResponse(content=ms_asdict(BaseResponse(success=True)))


# --- Internals --------------------------------------------------------------


def _event_payload(event: BuildProgressEvent) -> dict[str, Any]:
    """Convert one progress event to a JSON-friendly dict.

    Strips ``Path`` (-> string) and the ``type`` discriminator (carried
    separately on the wire as ``event_type``).
    """
    if not is_dataclass(event):  # pragma: no cover - typing safety
        return {}
    raw = asdict(event)
    raw.pop("type", None)
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if isinstance(v, Path):
            out[k] = str(v)
        else:
            out[k] = v
    return out
