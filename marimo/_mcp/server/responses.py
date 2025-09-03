# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Any, Literal, Optional, TypedDict, TypeVar

T = TypeVar("T")

if sys.version_info >= (3, 11):
    # Python 3.11+ supports TypedDict with Generic
    from typing import Generic

    class SuccessResult(TypedDict, Generic[T]):
        status: Literal["success", "error", "warning"]
        data: T
        auth_required: bool  # whether the tool requires authentication
        next_steps: Optional[list[str]]  # additional instructions for the LLM
        action_url: Optional[str]  # e.g., OAuth/link flow
        message: Optional[str]  # additional unstructured message
        meta: Optional[dict[str, Any]]  # additional structured context
else:
    # Python 3.10 fallback: Use Protocol for generic typing
    from typing import Generic, Protocol

    class SuccessResult(Protocol[T]):
        status: Literal["success", "error", "warning"]
        data: T
        auth_required: bool
        next_steps: Optional[list[str]]
        action_url: Optional[str]
        message: Optional[str]
        meta: Optional[dict[str, Any]]


def make_tool_success_result(
    data: T,
    *,
    status: Literal["success", "error", "warning"] = "success",
    auth_required: bool = False,
    next_steps: Optional[list[str]] = None,
    action_url: Optional[str] = None,
    message: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> SuccessResult[T]:
    """
    LLM-friendly success payload with explicit instructions.

    Returns a properly typed SuccessResult that FastMCP can validate.
    """
    # Return a dict that matches the SuccessResult structure
    # Type checkers will see this as SuccessResult[T]
    return {  # type: ignore[return-value]
        "status": status,
        "data": data,
        "auth_required": auth_required,
        "next_steps": next_steps,
        "action_url": action_url,
        "message": message,
        "meta": meta,
    }
