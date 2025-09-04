# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional, cast

from marimo._ai._types import (
    ChatAttachment,
    ChatMessage,
    ChatMessageDict,
    ChatPart,
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
    parts: Optional[list[ChatPart]] = None
    if parts_dict is not None:
        parts = []
        for part_dict in parts_dict:
            if part_dict["type"] == "text":
                part_dict = cast(TextPartDict, part_dict)
                parts.append(TextPart(type="text", text=part_dict["text"]))
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
                        reasoning=part_dict["reasoning"],
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
        role=d["role"],
        content=d["content"],
        attachments=attachments,
        parts=parts,
    )
