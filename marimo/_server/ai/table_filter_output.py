# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from marimo._server.ai.table_filter import (
    JSON_OUTPUT_INSTRUCTIONS,
    TableFilterPrompt,
)
from marimo._server.models.completion import UIMessage

if TYPE_CHECKING:
    from typing_extensions import Self

TEXT_OUTPUT_INSTRUCTIONS = """Convert the user's request into one FQL filter or an explanation.
Return plain text with exactly one first-line marker: FQL or EXPLANATION.
Put the nonempty payload on the following lines. Do not return a JSON envelope.
Return raw FQL without Markdown fences or commentary after the FQL marker.
"""


class TableFilterOutputError(ValueError):
    """The model did not return a complete table-filter result."""


class TableFilterOutput(BaseModel):
    """One complete filter proposal or a reason that no filter is available."""

    model_config = ConfigDict(extra="forbid", strict=True)

    fql: str | None = Field(description="Raw FQL, or null for an explanation.")
    explanation: str | None = Field(
        description="A reason that the request cannot become a filter, or null."
    )

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if (self.fql is None) == (self.explanation is None):
            raise ValueError(
                "Exactly one of fql and explanation must contain text."
            )
        payload = self.fql if self.fql is not None else self.explanation
        if payload is None or not payload.strip():
            raise ValueError(
                "The table-filter result must contain nonempty text."
            )
        return self

    def as_text(self) -> str:
        """Encode the first-line marker without changing the payload."""
        if self.fql is not None:
            return f"FQL\n{self.fql}"
        return f"EXPLANATION\n{self.explanation}"


def decode_table_filter_text(text: str) -> TableFilterOutput:
    """Decode only the first line and preserve the payload exactly.

    Args:
        text (str): A complete response with an FQL or EXPLANATION marker.
    """
    marker, separator, payload = text.partition("\n")
    marker = marker.removesuffix("\r")
    if not separator or marker not in {"FQL", "EXPLANATION"}:
        raise TableFilterOutputError(
            "The table-filter response must start with FQL or EXPLANATION "
            "on a separate line."
        )
    try:
        return TableFilterOutput(
            fql=payload if marker == "FQL" else None,
            explanation=payload if marker == "EXPLANATION" else None,
        )
    except ValidationError as error:
        raise TableFilterOutputError(
            "The table-filter response must contain nonempty text after the marker."
        ) from error


def table_filter_text_prompt(prompt: TableFilterPrompt) -> TableFilterPrompt:
    """Use marker-based instructions and examples for a text-only model.

    Args:
        prompt (TableFilterPrompt): The prompt with JSON result examples.
    """
    messages: list[UIMessage] = []
    for message in prompt.messages:
        if message["role"] == "assistant":
            output = TableFilterOutput.model_validate_json(
                message["parts"][0]["text"]
            )
            messages.append(
                {
                    **message,
                    "parts": [{"type": "text", "text": output.as_text()}],
                }
            )
        else:
            messages.append(message)
    return replace(
        prompt,
        system_prompt=prompt.system_prompt.replace(
            JSON_OUTPUT_INSTRUCTIONS, TEXT_OUTPUT_INSTRUCTIONS, 1
        ),
        messages=messages,
    )
