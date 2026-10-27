# Misc ✨ 

A hodgepodge of examples!

> [!TIP]
> Submit a
> [pull request](https://github.com/marimo-team/marimo/pulls) to add an example!

## Running examples

The requirements of each notebook are serialized in them as a top-level
comment. Here are the steps to open an example notebook:

1. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
2. Open an example with `uvx marimo edit --sandbox <notebook.py>`.

> [!TIP]
> The [`--sandbox` flag](https://docs.marimo.io/guides/editor_features/package_management.html) opens the notebook in an isolated virtual environment,
> automatically installing the notebook's dependencies 📦

You can also open notebooks without `uv`, with just `marimo edit <notebook.py>`;
however, you'll need to install the requirements yourself.

The [R](pixi_r.py) and [FFmpeg](pixi_ffmpeg.py) examples use Pixi to install
non-Python dependencies. With [Pixi installed](https://pixi.prefix.dev/latest/installation/),
run:

```bash
marimo edit --sandbox=pixi examples/misc/pixi_r.py
marimo edit --sandbox=pixi examples/misc/pixi_ffmpeg.py
```
