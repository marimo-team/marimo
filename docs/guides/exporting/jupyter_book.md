# Publishing with Jupyter Book

[Jupyter Book](https://jupyterbook.org/) is an open-source publishing system for
computational books, documentation, and course materials built from MyST Markdown
and notebooks.

marimo's [`jupyter-book-marimo`](https://github.com/marimo-team/jupyter-book-marimo)
plugin lets Jupyter Book render MyST-native `{marimo}` directives as hydrated
marimo islands. Use it when you want marimo cells and outputs inside a Jupyter
Book site.

Write a marimo cell with an explicit language:

````markdown
```{marimo} python
import marimo as mo

mo.md("hello")
```
````

For installation, page-level configuration, and supported directive options, see
the [jupyter-book-marimo docs](https://marimo-team.github.io/jupyter-book-marimo/).
