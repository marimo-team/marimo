# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output import md
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._runtime import output


class GoogleAiFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "google"

    def register(self) -> None:
        try:
            import google.generativeai as genai
        except (ImportError, ModuleNotFoundError):
            return

        from marimo._output import formatting

        @formatting.formatter(genai.types.GenerateContentResponse)
        def _show_response(
            response: genai.types.GenerateContentResponse,
        ) -> tuple[KnownMimeType, str]:
            if hasattr(response, "_iterator") and response._iterator is None:
                return ("text/html", md.md(response.text).text)
            else:
                # Streaming response
                total_text = ""
                for chunk in response:
                    total_text += chunk.text
                    output.replace(
                        md.md(_ensure_closing_code_fence(total_text))
                    )
                return ("text/html", md.md(total_text).text)


def _ensure_closing_code_fence(text: str) -> str:
    """Ensure text has an even number of code fences

    If text ends with an unclosed code fence, add a closing fence.
    Handles nested code fences by checking if the last fence is an opening one.
    """
    # Split by code fences to track nesting
    parts = text.split("```")
    # If odd number of parts, we have an unclosed fence
    # parts = ["before", "code", "between", "more code"] -> 4 parts = 3 fences
    # parts = ["before", "code", "between", "more code", "after"] -> 5 parts = 4 fences
    if len(parts) > 1 and len(parts) % 2 == 0:
        return text + "\n```"
    return text
