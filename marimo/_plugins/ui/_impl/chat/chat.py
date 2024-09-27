from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Final, List, Optional

from marimo._output.formatting import as_html
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.chat.convert import model_from_callable
from marimo._plugins.ui._impl.chat.types import (
    ChatMessage,
    ChatModel,
    ChatModelConfig,
    from_chat_message_dict,
)
from marimo._runtime.functions import EmptyArgs, Function


@dataclass
class SendMessageRequest:
    messages: List[ChatMessage]
    config: ChatModelConfig


@dataclass
class GetChatHistoryResponse:
    messages: List[ChatMessage]


DEFAULT_SYSTEM_MESSAGE = (
    "You are a helpful assistant specializing in data science."
)


@mddoc
class chat(UIElement[Dict[str, Any], List[ChatMessage]]):
    """
    A chatbot UI element for interactive conversations.

    **Example - Using a custom model.**

    You can define a custom chat model that takes a
    prompt, previous messages, and optional attachments as input
    and returns a response.

    The response can be an object, a marimo UI element, or a string.

    ```python
    def my_rag_model(prompt, messages, attachments):
        docs = find_docs(prompt)
        prompt = template(prompt, docs, messages)
        response = query(prompt)
        if is_dataset(response):
            return dataset_to_chart(response)
        return response


    chat = mo.ai.chatbot(
        my_rag_model,
        system_message="You are a helpful assistant.",
    )
    ```

    **Example - Using a built-in model.**

    You can use a built-in model from the `mo.ai` module.

    ```python
    chat = mo.ai.chatbot(
        mo.ai.openai("gpt-4o"),
        system_message="You are a helpful assistant.",
    )
    ```

    **Attributes.**

    - `value`: the current chat history

    **Initialization Args.**

    - `model`: the chatbot model
    - `system_message`: the initial system message for the chatbot
    - `prompts`: optional list of prompts to start the conversation
    - `on_message`: optional callback function to handle new messages
    - `max_tokens`: maximum number of tokens in the response
    - `temperature`: sampling temperature for response generation
    """

    _name: Final[str] = "marimo-chatbot"

    def __init__(
        self,
        model: ChatModel,
        *,
        system_message: str = DEFAULT_SYSTEM_MESSAGE,
        prompts: Optional[List[str]] = None,
        on_message: Optional[Callable[[List[ChatMessage]], None]] = None,
        show_configuration_controls: bool = False,
        max_tokens: int = 100,
        temperature: float = 0.5,
        top_p: float = 1,
        top_k: int = 40,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
    ) -> None:
        if callable(model):
            self._model = model_from_callable(model)
        else:
            self._model = model
        self._system_message = system_message
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._chat_history: List[ChatMessage] = [
            ChatMessage(role="system", content=system_message)
        ]

        super().__init__(
            component_name=chat._name,
            initial_value={"messages": self._chat_history},
            on_change=on_message,
            label="",
            args={
                "prompts": prompts,
                "system-message": system_message,
                "show-configuration-controls": show_configuration_controls,
                # Config
                "max-tokens": max_tokens,
                "temperature": temperature,
                "top-p": top_p,
                "top-k": top_k,
                "frequency-penalty": frequency_penalty,
                "presence-penalty": presence_penalty,
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
        content = (
            as_html(response).text  # convert to html if not a string
            if not isinstance(response, str)
            else response
        )
        self._chat_history = messages + [
            ChatMessage(role="assistant", content=content)
        ]

        self._value = self._chat_history
        if self._on_change:
            self._on_change(self._value)

        return content

    def _convert_value(self, value: Dict[str, Any]) -> List[ChatMessage]:
        if not isinstance(value, dict) or "messages" not in value:
            raise ValueError("Invalid chat history format")

        messages = value["messages"]
        return [from_chat_message_dict(msg) for msg in messages]
