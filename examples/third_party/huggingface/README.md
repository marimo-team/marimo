# HuggingFace 📦

These examples showcase how to use HuggingFace's models in marimo.

- You can find a list of these models [here](https://huggingface.co/models).
- These examples are easily deployable on [HuggingFace's Spaces](https://huggingface.co/new-space?template=marimo-team%2Fmarimo-app-template). Or check out our templates:
  - [Basic application template](https://huggingface.co/spaces/marimo-team/marimo-app-template/tree/main)
  - [Chatbot template](https://huggingface.co/spaces/marimo-team/marimo-chatbot-template/tree/main)
  - [Text-to-image template](https://huggingface.co/spaces/marimo-team/marimo-text-to-image-template/tree/main)

> [!TIP]
> Submit a
> [pull request](https://github.com/marimo-team/marimo/pulls) to add an example!

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
