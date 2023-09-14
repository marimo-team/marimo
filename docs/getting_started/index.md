# Getting Started

Installing marimo gets you the `marimo` command-line interface (CLI), the 
entry point to all things marimo.

## Installation

In a terminal, run

```bash
pip install marimo
marimo tutorial intro
```

You should see a tutorial notebook in your browser:

<div align="center">
<img src="https://github.com/marimo-team/marimo/blob/main/docs/_static/intro_tutorial.gif" width="400px" />
</div>

If that doesn't work, please [open a Github issue](https://github.com/marimo-team/marimo/issues).

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

- create or edit a notebook with a given name:

```bash
marimo edit your_notebook.py
```

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

Because marimo is different from traditional notebooks, your converted
notebook will likely have errors that you'll need to fix. marimo
will guide you through fixing them when you open it with `marimo edit`.

## VS Code extension

If you prefer VS Code over terminal, try the marimo
[VS Code extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo).
Use this extension to edit and run notebooks directly from VS Code, and to list
all marimo notebooks in your current directory.

<div align="center">
<figure>
<img src="/_static/vscode-marimo.png"/>
</figure>
</div>
