from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Final, List, Optional

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.chat.types import (
    ChatClientMessage,
    ChatModel,
    SendMessageRequest,
)
from marimo._runtime.functions import EmptyArgs, Function


@dataclass
class GetChatHistoryResponse:
    messages: List[ChatClientMessage]


DEFAULT_SYSTEM_MESSAGE = (
    "You are a helpful assistant specializing in data science."
)


@mddoc
class chat(UIElement[Dict[str, Any], List[ChatClientMessage]]):
    """
    A chatbot UI element for interactive conversations.

    **Example.**

    ```python
    chat = mo.ai.chatbot(
        model=mo.ai.openai("gpt-4o"),
        system_message="You are a helpful assistant.",
    )
    ```

    **Attributes.**

    - `value`: the current chat history

    **Initialization Args.**

    - `model`: the chatbot model
    - `system_message`: the initial system message for the chatbot
    - `on_message`: optional callback function to handle new messages
    - `max_tokens`: maximum number of tokens in the response
    - `temperature`: sampling temperature for response generation
    """

    _name: Final[str] = "marimo-chatbot"

    def __init__(
        self,
        model: ChatModel,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        on_message: Optional[Callable[[List[ChatClientMessage]], None]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> None:
        self._model = model
        self._system_message = system_message
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._chat_history: List[ChatClientMessage] = [
            ChatClientMessage(role="system", content=system_message)
        ]

        super().__init__(
            component_name=chat._name,
            initial_value={"messages": self._chat_history},
            on_change=on_message,
            label="",
            args={
                "system-message": system_message,
                "max-tokens": max_tokens,
                "temperature": temperature,
            },
            functions=(
                Function(
                    name=self.get_chat_history.__name__,
                    arg_cls=EmptyArgs,
                    function=self.get_chat_history,
                ),
                Function(
                    name=self.send_prompt.__name__,
                    arg_cls=SendMessageRequest,
                    function=self.send_prompt,
                ),
            ),
        )

    def get_chat_history(self, _args: EmptyArgs) -> GetChatHistoryResponse:
        return GetChatHistoryResponse(messages=self._chat_history)

    def send_prompt(self, args: SendMessageRequest) -> str:
        messages = args.messages

        response = self._model.generate_text(messages, args.config)
        self._chat_history = messages + [
            ChatClientMessage(role="assistant", content=response)
        ]

        self._value = self._chat_history
        if self._on_change:
            self._on_change(self._value)

        return response

    def _convert_value(self, value: Dict[str, Any]) -> List[ChatClientMessage]:
        if not isinstance(value, dict) or "messages" not in value:
            raise ValueError("Invalid chat history format")

        messages = value["messages"]
        return [ChatClientMessage.from_dict(msg) for msg in messages]
