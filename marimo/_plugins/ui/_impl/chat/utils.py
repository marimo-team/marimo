# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional, Union

from marimo._ai._types import (
    ChatAttachment,
    ChatMessage,
    ChatMessageDict,
    ReasoningDetails,
    ReasoningPart,
    TextPart,
    ToolInvocationPart,
    ToolInvocationResult,
)


def from_chat_message_dict(d: ChatMessageDict) -> ChatMessage:
    if isinstance(d, ChatMessage):
        return d

    attachments_dict = d.get("attachments", None)
    attachments: Optional[list[ChatAttachment]] = None
    if attachments_dict is not None:
        attachments = [
            ChatAttachment(
                name=attachment["name"] or "attachment",
                content_type=attachment["content_type"],
                url=attachment["url"],
            )
            for attachment in attachments_dict
        ]
    else:
        attachments = None

    # Handle parts
    parts_dict = d.get("parts", None)
    parts: Optional[
        list[Union[TextPart, ReasoningPart, ToolInvocationPart]]
    ] = None
    if parts_dict is not None:
        parts = []
        for part_dict in parts_dict:
            if part_dict["type"] == "text":
                parts.append(TextPart(type="text", text=part_dict["text"]))
            elif part_dict["type"] == "reasoning":
                # Handle ReasoningDetails if present
                details_list = part_dict.get("details", [])
                details = []

                if details_list:
                    for details_dict in details_list:
                        details.append(
                            ReasoningDetails(
                                type=details_dict["type"],
                                text=details_dict["text"],
                                signature=details_dict.get("signature"),
                            )
                        )
                else:
                    # Fallback for backward compatibility
                    details = [
                        ReasoningDetails(
                            type="text",
                            text=part_dict["reasoning"],
                            signature=None,
                        )
                    ]

                parts.append(
                    ReasoningPart(
                        type="reasoning",
                        reasoning=part_dict["reasoning"],
                        details=details,
                    )
                )
            elif part_dict["type"] == "tool-invocation":
                tool_inv = part_dict["tool_invocation"]
                if tool_inv["state"] == "result":
                    tool_call = ToolInvocationResult(
                        state=tool_inv["state"],
                        tool_call_id=tool_inv["tool_call_id"],
                        tool_name=tool_inv["tool_name"],
                        step=tool_inv["step"],
                        args=tool_inv["args"],
                        result=tool_inv["result"],
                    )
                    parts.append(
                        ToolInvocationPart(
                            type="tool-invocation", tool_invocation=tool_call
                        )
                    )
                else:
                    # Skip unsupported tool invocation states
                    continue

    return ChatMessage(
        role=d["role"],
        content=d["content"],
        attachments=attachments,
        parts=parts,
    )
