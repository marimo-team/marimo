# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._ai._tools.types import CodeExecutionResult
from marimo._server.ai.skills.utils import load_reference
from marimo._server.api.deps import AppState
from marimo._server.api.utils import get_code_mode_credentials
from marimo._server.scratchpad import run_scratchpad_code

if TYPE_CHECKING:
    from pydantic_ai import FunctionToolset
    from pydantic_ai.capabilities import Capability
    from starlette.requests import Request

    from marimo._session.session import Session


def build_execute_code_toolset(
    session: Session,
    request: Request,
) -> FunctionToolset[None]:
    """Build a `FunctionToolset` exposing one tool: `execute_code`.

    The tool is bound to the caller's *session* and *request*; the model
    never sees or passes a session id. Screenshot credentials are derived
    per tool call from the request so `ctx.screenshot()` can call back
    into this server (see `marimo/_code_mode/_context.py`).
    """

    from pydantic_ai import FunctionToolset

    toolset: FunctionToolset[None] = FunctionToolset()

    async def execute_code(code: str) -> CodeExecutionResult:
        """Run Python inside the running notebook's kernel scratchpad.

        Use this for all notebook mutations via `marimo._code_mode`.
        """
        server_url, auth_token = get_code_mode_credentials(
            AppState(request), request
        )
        return await run_scratchpad_code(
            session,
            request,
            code=code,
            server_url=server_url,
            auth_token=auth_token,
        )

    toolset.add_function(
        execute_code,
        name="execute_code",
        description=execute_code.__doc__,
    )
    return toolset


def references_capability() -> list[Capability]:
    from pydantic_ai.capabilities import Capability

    gotchas_capability: Capability = Capability(
        id="gotchas",
        description=(
            "Name redefinition, cached module proxies, and other notebook traps."
        ),
        instructions=load_reference("gotchas"),
        defer_loading=True,
    )

    notebook_improvements_capability: Capability = Capability(
        id="notebook-improvements",
        description="Improving, optimizing, or cleaning up an existing notebook.",
        instructions=load_reference("notebook-improvements"),
        defer_loading=True,
    )

    rich_representations_capability: Capability = Capability(
        id="rich-representations",
        description="Custom widgets, visual encodings, and interactive output.",
        instructions=load_reference("rich-representations"),
        defer_loading=True,
    )

    return [
        gotchas_capability,
        notebook_improvements_capability,
        rich_representations_capability,
    ]
