# Getting Started

Installing marimo gets you the `marimo` command-line interface (CLI), the entry point to all things marimo.

## Installation

Before installing marimo, we recommend creating and activating a Python
[virtual environment](https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments).

```{dropdown} Setting up a virtual environment

Python uses virtual environments to minimize conflicts among packages.
Here's a quickstart for `pip` users. If you use `conda`, please use a
[`conda` environment](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-with-commands) instead.

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
```

To install marimo, run the following in a terminal:

::::{tab-set}
:::{tab-item} install with pip

```bash
pip install marimo
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

Having installation issues? Reach out to us [at Github](https://github.com/marimo-team/marimo/issues) or [on Discord](https://discord.gg/JE7nhX6mD8).
```

## Tutorials

`marimo tutorial intro` opens the intro tutorial. List all tutorials with

```bash
marimo tutorial --help
```

## Notebooks

Create and edit notebooks with `marimo edit`.

- create a new notebook:

```bash
marimo edit
```

- marimo saves notebooks as Python files, which you can edit using:

```bash
marimo edit your_notebook.py
```

(If `your_notebook.py` doesn't exist, marimo will create a blank notebook
named `your_notebook.py`.)

## Apps

Use `marimo run` to serve your notebook as an app, with Python code hidden and
uneditable.

```bash
marimo run your_notebook.py
```

## Convert Jupyter notebooks

Automatically translate Jupyter notebooks to marimo notebooks with `marimo convert`:

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

Because marimo is different from traditional notebooks, your converted notebook
will likely have errors that you'll need to fix. marimo will guide you through
fixing them when you open it with `marimo edit`.

## GitHub Copilot

The marimo editor natively supports [GitHub Copilot](https://copilot.github.com/),
an AI pair programmer, similar to VS Code.

_Get started with Copilot_:

1. Install [Node.js](https://nodejs.org/en/download).
2. Enable Copilot via the settings menu in the marimo editor.

_Note_: Copilot is not yet available in our conda distribution; please install
marimo using `pip` if you need Copilot.

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
