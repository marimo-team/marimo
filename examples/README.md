# Examples

This folder contains example marimo notebooks, meant to teach you how to
use marimo's features as well as inspire you to make awesome notebooks.


- 🖱️ [`ui/`](ui/): how to use UI elements or widgets
- 🛢️ [`sql/`](sql/): how to use SQL in marimo
- ⛲ [`control_flow/`](control_flow/): how to control cell execution and output display
- 📝 [`markdown/`](markdown/): how to write markdown, including dynamic markdown
- 📽️ [`layouts/`](layouts/): how to present notebooks as slides, add sidebars, and more
- 🤖 [`ai/`](ai/): AI-related examples
- 🧪 [`testing/`](testing/): how to test marimo notebooks, and use marimo notebooks as tests
- 📦 [`third_party/`](third_party/): using popular third-party packages in marimo
- ☁️  [`cloud/`](cloud/): using various cloud providers
- 🧩 [`frameworks/`](frameworks/): integrating with different frameworks (web/ASGI)
- ✨ [`misc/`](misc/): miscellaneous topical examples

> [!TIP]
> New to marimo? Run `marimo tutorial intro` at the command line first!

> [!TIP]
> Check out our [public gallery](https://marimo.io/gallery) of interactive
> notebooks to get inspired.

> [!NOTE]
> Submit a
> [pull request](https://github.com/marimo-team/marimo/pulls) to add an example!
> We especially welcome library developers to add examples to `third_party/`.

## Running examples

The requirements of each notebook are serialized in them as a top-level
comment. Here are the steps to open an example notebook:

1. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
2. Open an example with `marimo edit --sandbox <notebook-url>`.

For example:

```bash
uvx marimo edit --sandbox https://github.com/marimo-team/marimo/blob/main/examples/misc/seam_carving.py
```

> [!TIP]
> The [`--sandbox` flag](https://docs.marimo.io/guides/editor_features/package_management.html) opens the notebook in an isolated virtual environment,
> automatically installing the notebook's dependencies 📦

You can also open notebooks without `uv`, in which case you'll need to
manually [install marimo](https://docs.marimo.io/getting_started/index.html#installation)
first. Then run `marimo edit <notebook.py>`; however, you'll also need to
install the requirements yourself.

## More examples 🌟

Every week, we highlight stellar examples and projects from our community.
Check them out at our [marimo spotlights](https://github.com/marimo-team/spotlights)
repo!
