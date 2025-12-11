# Chat 💬

These examples show how to make chatbots with marimo, using [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat).

- `custom.py` shows how to make a custom chatbot.
- `streaming_custom.py` shows how to make a custom chatbot with streaming responses (delta-based).
- `openai_example.py` shows how to make a chatbot powered by OpenAI models (streaming by default).
- `anthropic_example.py` shows how to make a chatbot powered by Anthropic models (streaming by default).
- `gemini.py` shows how to make a chatbot powered by Google models like Gemini (streaming by default).
- `groq_example.py` shows how to make a chatbot powered by Groq models (streaming by default).
- `mlx_chat.py` shows a simple chatbot using local on-device models with Apple's [MLX](https://github.com/ml-explore/mlx), a machine learning framework from Apple that is similar to JAX and PyTorch. This specific example uses the [mlx-lm](https://github.com/ml-explore/mlx-examples/tree/main/llms) library. Note that Apple Silicon chips are required for using MLX.
- `llm_datasette.py` shows how to make a chatbot powered by Simon W's LLM library.
- `dagger_code_interpreter.py` shows how to make a basic code-interpreter chatbot powered by Dagger containers.
- `recipe_bot.py` shows how to make a chatbot that can parse recipes from images.
- `simplemind_example.py` shows how to integrate [simplemind](https://github.com/kennethreitz/simplemind).
- `generative_ui.py` shows how to make a chatbot that can generate UI code.

## Streaming Responses

All built-in models (OpenAI, Anthropic, Google, Groq, Bedrock) stream responses using delta-based streaming. If a model doesn't support streaming, it will automatically fall back to non-streaming mode.

For custom models, create an async generator function that yields delta chunks (new content only).

See `streaming_custom.py` for a complete example of custom streaming.

Chatbot's in marimo are _reactive_: when the chatbot responds with a message,
all other cells referencing the chatbot are automatically run or marked
stale, with the chatbot's response stored in the object's `value` attribute.
You can use this to make notebooks that respond to the chatbot's response
in arbitrary ways. For example, you can make agentic notebooks!

Once you understand the basics, for a more interesting example, check out
[our notebook that lets you talk to any GitHub repo](../../third_party/sage/),
powered by [storia-ai/sage](https://github.com/storia-ai/sage). This example demonstrates advanced usage
of `ui.chat`, using `langchain` to construct a RAG-powered chatbot, served by
an async generator callback function.

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
