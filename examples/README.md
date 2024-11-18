# Examples

This folder contains example marimo notebooks.

- 🖱️ [`ui/`](ui/): marimo's many UI elements or widgets
- 🛢️ [`sql/`](sql/): using marimo's SQL cells
- 📽️ [`layouts/`](layouts/): present notebooks as slides, add sidebars, and more
- 🤖 [`ai/`](ai/): AI-related examples
- 📦 [`third_party/`](third_party/): using popular third-party packages in marimo
- ☁️  [`cloud/`](cloud/): using various cloud providers
- 🧩 [`frameworks/`](frameworks/): integrating with different frameworks (web/ASGI)
- ✨ [`misc/`](misc/): miscellaneous topical examples

> [!TIP]
> New to marimo? Run `marimo tutorial ui` at the command line first!

> [!NOTE]
> Submit a
> [pull request](https://github.com/marimo-team/marimo/pulls) to add an example!
> We especially welcome library developers to add examples to `third_party/`.


## Running examples

The requirements of each notebook are serialized in them as a top-level
comment. Here are the steps to open an example notebook:

1. [Install marimo](https://docs.marimo.io/getting_started/index.html#installation)
2. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
3. Open an example with `marimo edit --sandbox <notebook-url>`.

For example:

```bash
marimo edit --sandbox https://github.com/marimo-team/marimo/blob/main/examples/ui/reactive_plots.py
```

> [!TIP]
> The [`--sandbox` flag](https://docs.marimo.io/guides/editor_features/package_management.html) opens the notebook in an isolated virtual environment,
> automatically installing the notebook's dependencies 📦

You can also open notebooks without `uv`, with just `marimo edit <notebook.py>`;
however, you'll need to install the requirements yourself.

## More examples 🌟

Every week, we highlight stellar examples and projects from our community.
Check them out at our [marimo spotlights](https://github.com/marimo-team/spotlights)
repo!
