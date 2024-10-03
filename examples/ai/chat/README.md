# Chat 💬

These examples show how to make chatbots with marimo, using [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat).

- `custom.py` shows how to make a custom chatbot
- `openai.py` shows how to make a chatbot powered by OpenAI models
- `anthropic.py` shows how to make a chatbot powered by Anthropic models
- `google.py` shows how to make a chatbot powered by Google models like Gemini

Chatbot's in marimo are _reactive_: when the chatbot responds with a message,
all other cells referencing the chatbot are automatically run or marked
stale, with the chatbot's response stored in the object's `value` attribute.
You can use this to make notebooks that respond to the chatbot's response
in arbitrary ways. For example, you can make agentic notebooks!

## Running examples

The requirements of each notebook are serialized in them as a top-level
comment. Here are the steps to open an example notebook:

1. [Install marimo](https://docs.marimo.io/getting_started/index.html#installation)
2. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
3. Open an example with `marimo edit --sandbox <notebook.py>`.

> [!TIP]
> The [`--sandbox` flag](https://docs.marimo.io/guides/editor_features/package_management.html) opens the notebook in an isolated virtual environment,
> automatically installing the notebook's dependencies 📦

You can also open notebooks without `uv`, with just `marimo edit <notebook.py>`;
however, you'll need to install the requirements yourself.
