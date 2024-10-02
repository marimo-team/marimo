from __future__ import annotations

from marimo._plugins.ui._impl.chat.llm import simple
from marimo._plugins.ui._impl.chat.types import ChatMessage, ChatModelConfig


def test_simple_model():
    model = simple(lambda x: x * 2)
    assert (
        model([ChatMessage(role="user", content="hey")], ChatModelConfig())
        == "heyhey"
    )

    assert (
        model(
            [
                ChatMessage(role="user", content="hey", attachments=[]),
                ChatMessage(role="user", content="goodbye", attachments=[]),
            ],
            ChatModelConfig(),
        )
        == "goodbyegoodbye"
    )
