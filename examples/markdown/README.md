# Markdown

These basic examples show how to use write markdown in marimo.

> [!TIP]
> New to marimo? Run `marimo tutorial intro` and `marimo tutorial markdown`
> at the command line first!

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
