# Markdown

Export marimo notebooks to markdown.

!!! warning "Outputs are not included"

    Markdown export only includes the notebook source code (code and markdown cells). Cell outputs are not saved in the exported markdown. To include outputs, export to [static HTML](static_html.md) or [Jupyter notebook](jupyter_notebook.md) instead.

## Export from the marimo editor

Export from the notebook settings menu, in the top right.

<div align="center">
<figure>
<img src="/_static/docs-md-export.png" width="65%"/>
<figcaption>Download as static HTML.</figcaption>
</figure>
</div>


## Export from the command line

Export to markdown in top to bottom order, so the cells are in the
order as they appear in the notebook.

```bash
marimo export md notebook.py -o notebook.md
```

This can be useful to plug into other tools that read markdown, such as [Quarto](https://quarto.org/) or [MyST](https://myst-parser.readthedocs.io/).

!!! tip "marimo can open markdown files as notebooks"
    Learn more with `marimo tutorial markdown-format` at the command line.

## Convert markdown back to a marimo notebook

You can also convert the markdown back to a marimo notebook:

```bash
marimo convert notebook.md > notebook.py
```
