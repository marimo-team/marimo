# AI 🤖

These examples showcase a few simple applications of AI.

- 💬 [`chat/`](chat/): creating chatbots with marimo, using [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat)
- 🛢️ [`data/`](data/): making data labeling and model comparison tools
- 🛠 [`tools/`](tools/): interacting with external functions and services with function calling, returning rich responses
- 🍿 [`misc/`](misc/): miscellaneous AI examples

> [!TIP]
> Submit a
> [pull request](https://github.com/marimo-team/marimo/pulls) to add an example!

## Running examples

The requirements of each notebook are serialized in them as a top-level
comment. Here are the steps to open an example notebook:

1. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
2. Open an example with `uvx marimo edit --sandbox <notebook-url>`

> [!TIP]
> The [`--sandbox` flag](https://docs.marimo.io/guides/editor_features/package_management.html) opens the notebook in an isolated virtual environment,
> automatically installing the notebook's dependencies 📦

You can also open notebooks without `uv`, in which case you'll need to
manually [install marimo](https://docs.marimo.io/getting_started/index.html#installation)
first. Then run `marimo edit <notebook-url>`; however, you'll also need to
install the requirements yourself.
