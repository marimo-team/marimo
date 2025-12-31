# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import cast

from marimo._ai._types import (
    ChatMessage,
    ChatMessageDict,
    ChatPart,
    FilePart,
    FilePartDict,
    ReasoningDetails,
    ReasoningPart,
    ReasoningPartDict,
    TextPart,
    TextPartDict,
    ToolInvocationPart,
    ToolInvocationPartDict,
)


def from_chat_message_dict(d: ChatMessageDict) -> ChatMessage:
    if isinstance(d, ChatMessage):
        return d

    # Handle parts
    parts_dict = d.get("parts", None)
    parts: list[ChatPart] = []
    if parts_dict is not None:
        parts = []
        for part_dict in parts_dict:
            if part_dict["type"] == "text":
                part_dict = cast(TextPartDict, part_dict)
                parts.append(TextPart(type="text", text=part_dict["text"]))
            elif part_dict["type"] == "file":
                part_dict = cast(FilePartDict, part_dict)
                parts.append(
                    FilePart(
                        type="file",
                        media_type=part_dict["media_type"],
                        filename=part_dict["filename"],
                        url=part_dict["url"],
                    )
                )
            elif part_dict["type"] == "reasoning":
                part_dict = cast(ReasoningPartDict, part_dict)
                # Handle ReasoningDetails if present
                details_list = part_dict.get("details", [])
                details: list[ReasoningDetails] = []

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
                        text=part_dict["reasoning"],
                        details=details,
                    )
                )
            elif part_dict["type"].startswith("tool-"):
                part_dict = cast(ToolInvocationPartDict, part_dict)
                tool_inv = ToolInvocationPart(
                    type=part_dict["type"],
                    tool_call_id=part_dict["tool_call_id"],
                    state=part_dict["state"],
                    input=part_dict["input"],
                    output=part_dict.get("output"),
                )
                parts.append(
                    ToolInvocationPart(
                        type=tool_inv.type,
                        tool_call_id=tool_inv.tool_call_id,
                        state=tool_inv.state,
                        input=tool_inv.input,
                        output=tool_inv.output,
                    )
                )

    return ChatMessage(
        id=d.get("id", ""),
        role=d["role"],
        content=d["content"],
        parts=parts,
        metadata=d.get("metadata"),
    )
