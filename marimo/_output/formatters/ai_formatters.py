# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output import md
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.stateless import plain_text
from marimo._runtime import output

LOGGER = _loggers.marimo_logger()


class GoogleAiFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "google"

    def register(self) -> None:
        try:
            import google.generativeai as genai  # type: ignore
        except (ImportError, ModuleNotFoundError):
            return

        from marimo._output import formatting

        @formatting.formatter(genai.types.GenerateContentResponse)
        def _show_response(
            response: genai.types.GenerateContentResponse,
        ) -> tuple[KnownMimeType, str]:
            if hasattr(response, "_iterator") and response._iterator is None:
                return md.md(response.text)._mime_()

            # Streaming response
            total_text = ""
            for chunk in response:
                total_text += chunk.text
                output.replace(md.md(_ensure_closing_code_fence(total_text)))
            return md.md(total_text)._mime_()


class OpenAIFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "openai"

    def register(self) -> None:
        import openai
        from openai.types.chat import ChatCompletion, ChatCompletionChunk
        from openai.types.completion import Completion

        from marimo._output import formatting

        @formatting.formatter(Completion)
        def _show_completion(
            response: Completion,
        ) -> tuple[KnownMimeType, str]:
            return md.md(response.choices[0].text)._mime_()

        @formatting.formatter(openai.Stream)
        def _show_stream(
            response: (
                openai.Stream[Completion] | openai.Stream[ChatCompletionChunk]
            ),
        ) -> tuple[KnownMimeType, str]:
            total_text: str = ""
            for chunk in response:
                if isinstance(chunk, Completion):
                    total_text += chunk.choices[0].text
                elif isinstance(chunk, ChatCompletionChunk):
                    if chunk.choices[0].delta.content:
                        total_text += chunk.choices[0].delta.content
                else:
                    LOGGER.warning(f"Unknown openai chunk type: {type(chunk)}")
                    # Fallback to the request
                    return plain_text.plain_text(repr(response))._mime_()

                output.replace(md.md(_ensure_closing_code_fence(total_text)))
            return md.md(total_text)._mime_()

        @formatting.formatter(ChatCompletion)
        def _show_chat_completion(
            response: ChatCompletion,
        ) -> tuple[KnownMimeType, str]:
            content = response.choices[0].message.content
            if content is not None:
                return md.md(content)._mime_()

            # Fallback to the request
            return plain_text.plain_text(repr(response))._mime_()


class TransformersFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "transformers"

    def register(self) -> None:
        from transformers import TextIteratorStreamer  # type: ignore

        from marimo._output import formatting

        @formatting.formatter(TextIteratorStreamer)
        def _show_text_iterator_streamer(
            streamer: TextIteratorStreamer,
        ) -> tuple[KnownMimeType, str]:
            total_text: str = ""
            for text in streamer:
                if isinstance(text, str):
                    total_text += text
                    output.replace(
                        md.md(_ensure_closing_code_fence(total_text))
                    )
            return md.md(total_text)._mime_()


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
