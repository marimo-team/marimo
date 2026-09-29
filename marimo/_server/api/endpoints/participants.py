# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
from starlette.authentication import requires
from starlette.responses import StreamingResponse

from marimo._messaging.participants import HandoffPayload, ParticipantMetadata
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.participants import (
    ParticipantAttachResponse,
    ParticipantDetachResponse,
    ParticipantEventsResponse,
    ParticipantHandoffResponse,
)
from marimo._server.router import APIRouter
from marimo._server.sse import (
    HEARTBEAT_EVENT,
    SSE_HEADERS,
    format_sse_event,
)
from marimo._session.participants import (
    HandoffTooLargeError,
    NoAttachedParticipantError,
    ParticipantRegistryClosedError,
)
from marimo._utils.http import HTTPException, HTTPStatus

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request

router = APIRouter()


def _optional_nonnegative_int(request: Request, name: str) -> int | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{name} must be a non-negative integer.",
        ) from error
    if value < 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{name} must be a non-negative integer.",
        )
    return value


@router.post("/attach")
@requires("edit")
async def attach(request: Request) -> ParticipantAttachResponse:
    """Attach or renew the participant identified by the request headers."""
    try:
        metadata = (
            await parse_request(request, cls=ParticipantMetadata)
            if await request.body()
            else None
        )
    except (msgspec.DecodeError, msgspec.ValidationError, ValueError) as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid participant metadata.",
        ) from error
    resolved = await AppState(request).require_participant_session(
        participant_required=True,
        attach_request=True,
        metadata=metadata,
    )
    assert resolved.participant is not None
    return ParticipantAttachResponse(
        participant_id=resolved.participant.participant_id,
        cursor=resolved.participant.cursor,
        attached=resolved.participant.attached,
        record_created=resolved.record_created,
        kind=resolved.participant.kind,
        harness=resolved.participant.harness,
    )


@router.post("/detach")
@requires("edit")
async def detach(request: Request) -> ParticipantDetachResponse:
    """End the participant attachment while retaining its record."""
    resolved = await AppState(request).require_participant_session(
        participant_required=True
    )
    assert resolved.participant is not None
    state = await resolved.session.participants.detach(
        resolved.participant.participant_id
    )
    return ParticipantDetachResponse(
        participant_id=state.participant_id,
        attached=state.attached,
    )


@router.get("/events")
@requires("edit")
async def events(request: Request) -> ParticipantEventsResponse:
    """Read retained handoffs and advance the participant cursor."""
    resolved = await AppState(request).require_participant_session(
        participant_required=True
    )
    assert resolved.participant is not None
    result = await resolved.session.participants.read_events(
        resolved.participant.participant_id,
        since=_optional_nonnegative_int(request, "since"),
        limit=_optional_nonnegative_int(request, "limit"),
    )
    return ParticipantEventsResponse(
        events=result.events,
        cursor=result.cursor,
        remaining=result.remaining,
    )


@router.get("/events/stream")
@requires("edit")
async def stream_events(request: Request) -> StreamingResponse:
    """Stream retained and future handoffs as server-sent events."""
    resolved = await AppState(request).require_participant_session(
        participant_required=True
    )
    assert resolved.participant is not None
    participant_id = resolved.participant.participant_id

    async def stream() -> AsyncGenerator[str, None]:
        async for event in resolved.session.participants.stream_events(
            participant_id
        ):
            if event is None:
                yield HEARTBEAT_EVENT
            else:
                yield format_sse_event(
                    msgspec.json.encode(event).decode(), event="handoff"
                )

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.post("/handoff")
@requires("edit")
async def handoff(request: Request) -> ParticipantHandoffResponse:
    """Append a browser-authored handoff for the live participant."""
    session = AppState(request).require_current_session_with_stable_id()
    payload = await parse_request(request, cls=HandoffPayload)
    try:
        event = await session.participants.append_handoff(payload)
    except NoAttachedParticipantError as error:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail="No participant is attached to this session.",
        ) from error
    except HandoffTooLargeError as error:
        raise HTTPException(
            status_code=HTTPStatus.PAYLOAD_TOO_LARGE,
            detail="Handoff payload exceeds the configured limit.",
        ) from error
    except ParticipantRegistryClosedError as error:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Session {session.stable_id} is closed.",
        ) from error
    return ParticipantHandoffResponse(seq=event.seq)
