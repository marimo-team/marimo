# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Generator

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import StreamingResponse

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.models.completion import AiCompletionRequest
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

# Router for file ai
router = APIRouter()


@router.post("/completion")
@requires("edit")
async def ai_completion(
    *,
    request: Request,
) -> StreamingResponse:
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="OpenAI not installed"
        ) from None

    app_state = AppState(request)
    app_state.require_current_session()
    body = await parse_request(request, cls=AiCompletionRequest)
    key = os.environ.get("OPENAI_API_KEY")

    if not key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="OpenAI API key not found in environment",
        )

    client = OpenAI(api_key=key)

    system_prompt = (
        "You are a helpful assistant that can answer questions "
        "about python code. You can only output python code. "
        "Do not describe the code, just write the code."
        "Do not output markdown or backticks."
    )

    prompt = body.prompt
    if body.include_other_code:
        prompt = (
            f"{prompt}\n\nCode from other cells:\n{body.include_other_code}"
        )
    if body.code.strip():
        prompt = f"{prompt}\n\nCurrent code:\n{body.code}"

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        stream=True,
    )

    # If it starts or ends with markdown, remove it
    def stream_response() -> Generator[str, None, None]:
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                if content.startswith("```python"):
                    yield content[9:]
                if content.startswith("```"):
                    yield content[4:]
                elif content.endswith("```"):
                    yield content[:-3]
                else:
                    yield content or ""

    return StreamingResponse(
        content=stream_response(),
        media_type="application/json",
    )
