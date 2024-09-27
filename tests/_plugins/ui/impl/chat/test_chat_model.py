from __future__ import annotations

from marimo._plugins.ui._impl.chat.convert import model_from_callable
from marimo._plugins.ui._impl.chat.models import simple
from marimo._plugins.ui._impl.chat.types import ChatMessage, ChatModelConfig


def test_model_from_callable_any_args():
    model = model_from_callable(lambda x, _y: f'you said: "{x[-1].content}"')
    assert (
        model.generate_text(
            [ChatMessage(role="user", content="hey")], ChatModelConfig()
        )
        == 'you said: "hey"'
    )


def test_model_from_callable_single_arg():
    model = model_from_callable(lambda x: f'you said: "{x[-1].content}"')
    assert (
        model.generate_text(
            [ChatMessage(role="user", content="hey")], ChatModelConfig()
        )
        == 'you said: "hey"'
    )


def test_simple_model():
    model = simple(lambda x: x * 2)
    assert (
        model.generate_text(
            [ChatMessage(role="user", content="hey")], ChatModelConfig()
        )
        == "heyhey"
    )

    assert (
        model.generate_text(
            [
                ChatMessage(role="user", content="hey", attachments=[]),
                ChatMessage(role="user", content="goodbye", attachments=[]),
            ],
            ChatModelConfig(),
        )
        == "goodbyegoodbye"
    )
