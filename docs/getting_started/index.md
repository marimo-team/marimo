# Getting Started

Installing marimo gets you the `marimo` command-line interface (CLI), the entry point to all things marimo.

## Installation

Before installing marimo, we recommend creating and activating a Python
[virtual environment](https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments).

```{dropdown} Setting up a virtual environment

Python uses virtual environments to minimize conflicts among packages.
Here's a quickstart for `pip` users. If you use `conda`, please use a [`conda`
environment](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-with-commands)
instead.

Run the following in the terminal:


- create an environment with `python -m venv marimo-env`
- activate the environment:
  - macOS/Unix: `source marimo-env/bin/activate`
  - Windows: `marimo-env\Scripts\activate`

_Make sure the environment is activated before installing marimo and when
using marimo._ Install other packages you may need, such as numpy, pandas, matplotlib,
and altair, in this environment. When you're done, deactivate the environment
with `deactivate` in the terimnal.

Learn more from the [official Python tutorial](https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments).

:::{admonition} Using uv?
:class: tip

[uv](https://github.com/astral-sh/uv) is a next-generation Python package
installer and manager that is 10-100x faster than pip, and also makes it easy
to install Python and manage projects. With `uv`, creating a virtual
environment is as easy as `uv venv`.
:::
```

To install marimo, run the following in a terminal:

::::{tab-set}
:::{tab-item} install with pip

```bash
pip install marimo
```

:::
:::{tab-item} install with uv

```bash
uv pip install marimo
```

:::
:::{tab-item} install with conda

```bash
conda install -c conda-forge marimo
```

:::
::::

To check if the install worked, run

```bash
marimo tutorial intro
```

A tutorial notebook should open in your browser.

```{admonition} Installation issues?

Having installation issues? Reach out to us [at GitHub](https://github.com/marimo-team/marimo/issues) or [on Discord](https://marimo.io/discord?ref=docs).
```

## Tutorials

`marimo tutorial intro` opens the intro tutorial. List all tutorials with

```bash
marimo tutorial --help
```

## Enable more features with optional dependencies

Some features require additional dependencies, which are not installed by default. This includes:

- [SQL cells](/guides/working_with_data/sql.md)
- Charts in the datasource viewer
- [AI features](/guides/editor_features/ai_completion.md)
- Format on save

To install the optional dependencies, run:

::::{tab-set}
:::{tab-item} install with pip

```bash
pip install "marimo[recommended]"
```

:::
:::{tab-item} install with uv

```bash
uv pip install "marimo[recommended]"
```

:::
:::{tab-item} install with conda

```bash
conda install -c conda-forge marimo duckdb altair polars openai ruff
```

:::
::::

This will install: `duckdb`, `altair`, `polars`, `openai`, and `ruff`.

## Edit notebooks

Create and edit notebooks with `marimo edit`.

- launch the notebook server to create new notebooks,
  and start or stop existing ones:

```bash
marimo edit
```

- create or edit a single notebook with

```bash
marimo edit your_notebook.py
```

(If `your_notebook.py` doesn't exist, marimo will create a blank notebook
named `your_notebook.py`.)

## Deploy as apps

Use `marimo run` to serve your notebook as an app, with Python code hidden and
uneditable.

```bash
marimo run your_notebook.py
```

## Convert from Jupyter to marimo

Automatically convert Jupyter notebooks to marimo notebooks with `marimo convert`:

```bash
marimo convert your_notebook.ipynb -o your_notebook.py
```

Then open the notebook with `marimo edit your_notebook.py`

:::{admonition} Disable autorun on startup
:class: tip

marimo automatically runs notebooks when they are opened. If this
is a problem for you (not all Jupyter notebooks are designed to be run on
startup), you can disable autorun on startup via [user configuration](/guides/configuration/runtime_configuration.md).

1. Type `marimo config show` to get the location of your config file.
2. If no config file exists, create it at `~/.marimo.toml` or `$XDG_CONFIG_HOME/marimo/marimo.toml`.
3. Update your config to include the following:

```toml
[runtime]
auto_instantiate = false
```

:::

## GitHub Copilot and AI Assistant

The marimo editor natively supports [GitHub Copilot](https://copilot.github.com/),
an AI pair programmer, similar to VS Code.

_Get started with Copilot_:

1. Install [Node.js](https://nodejs.org/en/download).
2. Enable Copilot via the settings menu in the marimo editor.

_Note_: Copilot is not yet available in our conda distribution; please install
marimo from `PyPI` if you need Copilot.

marimo also comes with support for [other copilots](/guides/editor_features/ai_completion.md#codeium-copilot),
and a built-in [AI assistant](/guides/editor_features/ai_completion.md#generate-code-with-our-ai-assistant) that helps you write code.

## VS Code extension

If you prefer VS Code over terminal, try our
[VS Code extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo).
Use this extension to edit and run notebooks directly from VS Code, and to list
all marimo notebooks in your current directory.

<div align="center">
<figure>
<img src="/_static/vscode-marimo.png"/>
</figure>
</div>
