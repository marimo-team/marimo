# Examples


This folder contains example marimo notebooks.

- 🖱️ `ui/`: marimo's many UI elements or widgets
- 🛢️ `sql/`: SQL and Python inter-op
- 🤖 `ai/`: AI-related examples
- 📦 `third_party/`: using popular third-party packages in marimo
- ☁️  `cloud/`: using various cloud providers
- ✨ `misc/`: miscellenous topical examples

> [!NOTE]
> Submit a
> [pull request](https://github.com/marimo-team/marimo/pulls) to add an example!
> We especially welcome library developers to add examples to `third_party/`.

> [!Tip]
> marimo ships with tutorials to help you get started: start with
> `marimo tutorial intro` at the command line.

## Running an example

The requirements of each notebook are serialized in them as a top-level
comment. Here are the steps to open an example notebook:

1. [Install marimo](https://docs.marimo.io/getting_started/index.html#installation)
2. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
3. Open an example with `marimo edit --sandbox <notebook.py>`.

> [!TIP]
> The `--sandbox` flag opens the notebook in an isolated virtual environment,
> automatically installing the notebook's dependencies 📦

