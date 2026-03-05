# Markdown

Export marimo notebooks to markdown.

## Export from the command line

Export to markdown in top to bottom order, so the cells are in the
order as they appear in the notebook.

```bash
marimo export md notebook.py -o notebook.md
```

This can be useful to plug into other tools that read markdown, such as [Quarto](https://quarto.org/) or [MyST](https://myst-parser.readthedocs.io/).

!!! tip "marimo can directly open markdown files as notebooks"
    Learn more with `marimo tutorial markdown-format` at the command line.

## Convert markdown back to a marimo notebook

You can also convert the markdown back to a marimo notebook:

```bash
marimo convert notebook.md > notebook.py
```
