# Examples

This folder contains example marimo notebooks, organized into folders.

- 🍃 `tutorials/`: get up and running with marimo
- 🖱️ `ui/`: marimo's many UI elements or widgets
- 🛢️ `sql/`: SQL and Python inter-op
- 🤖 `ai/`: AI-related examples
- ☁️  `cloud/`: using various cloud providers
- 📦 `third_party/`: a showcase of how to use popular third-party packages in marimo
- ✨ `misc/`: miscellenous topical examples

> [!NOTE]
> Submit a [pull request](https://github.com/marimo-team/marimo/pulls) to add
> an example to our repo. All contributions are welcome! 🙏

## Running an example

The requirements of each notebook are serialized in them as a top-level
comment. Here are the steps to open an example notebook:

1.[Install marimo](https://docs.marimo.io/getting_started/index.html#installation).
2.[Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation).
3. Open an example with `marimo edit --sandbox <notebook.py>`.

> [!TIP]
> The `--sandbox` flag will open the notebook in an isolated virtual environment,
> automatically installing the notebook's dependencies 📦
