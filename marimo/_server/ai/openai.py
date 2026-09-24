# Copyright 2026 Marimo. All rights reserved.
"""Responses API compatibility for #10794; imported lazily by providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openai import AsyncStream
from openai.types.responses import ResponseStreamEvent
from pydantic_ai.models.openai import (  # noqa: TID253 - module is loaded lazily
    OpenAIResponsesModel,
)

from marimo._utils.typing import override

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.models.openai import OpenAIResponsesStreamedResponse


class _ResponseStream(AsyncStream[ResponseStreamEvent]):
    def __init__(self, source: AsyncStream[ResponseStreamEvent]) -> None:
        self._source = source
        self.response = source.response
        self._iterator = self._events()

    async def _events(self) -> AsyncIterator[ResponseStreamEvent]:
        from pydantic_ai.exceptions import UnexpectedModelBehavior

        async for event in self._source:
            if getattr(event, "response", None) is None:
                # Empty interim updates carry no content, but a missing
                # terminal response must not be treated as success.
                if event.type in {
                    "response.created",
                    "response.in_progress",
                    "response.queued",
                }:
                    continue
                if event.type in {
                    "response.completed",
                    "response.failed",
                    "response.incomplete",
                }:
                    raise UnexpectedModelBehavior(
                        f"AI provider sent {event.type} without a response. "
                        "Please retry."
                    )
            yield event

    @override
    async def close(self) -> None:
        await self._source.close()


class SafeOpenAIResponsesModel(OpenAIResponsesModel):
    """Handle empty status events before Pydantic AI processes the stream."""

    @override
    async def _process_streamed_response(
        self,
        response: AsyncStream[ResponseStreamEvent],
        *args: Any,
        **kwargs: Any,
    ) -> OpenAIResponsesStreamedResponse:
        # Forward arguments unchanged across supported pydantic-ai versions.
        return await super()._process_streamed_response(
            _ResponseStream(response), *args, **kwargs
        )
