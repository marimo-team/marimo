from __future__ import annotations

from typing import Any, Generic, Literal, Optional, TypedDict, TypeVar, cast

T = TypeVar("T")


class SuccessResult(TypedDict, Generic[T]):
    status: Literal["success", "error", "warning"]
    data: T
    auth_required: bool  # whether the tool requires authentication
    next_steps: Optional[list[str]]  # additional instructions for the LLM
    action_url: Optional[str]  # e.g., OAuth/link flow
    message: Optional[str]  # additional unstructured message
    meta: Optional[dict[str, Any]]  # additional structured context


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
    """
    descriptive_success = cast(
        SuccessResult[T],
        {
            "status": status,
            "data": data,
            "auth_required": auth_required,
            "next_steps": next_steps,
            "action_url": action_url,
            "message": message,
            "meta": meta,
        },
    )
    # FastMCP automatically formats success responses to a proper MCP response
    return descriptive_success
