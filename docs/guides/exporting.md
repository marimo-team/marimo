# Exporting

Export marimo notebooks to other file formats at the command line using

```
marimo export
```

## Export to static HTML

Export the current view your notebook to static HTML via the notebook
menu:

<div align="center">
<figure>
<img src="/_static/docs-html-export.png"/>
<figcaption>Download as static HTML.</figcaption>
</figure>
</div>

You can also export to HTML at the command-line:

```bash
marimo export html notebook.py -o notebook.html
```

or watch the notebook for changes and automatically export to HTML:

```bash
marimo export html notebook.py -o notebook.html --watch
```

## Export to a Python script

Export to a flat Python script in topological order, so the cells adhere to
their dependency graph.

```bash
marimo export script notebook.py -o notebook.script.py
```

```{admonition} Top-level await not supported
:class: warning

Exporting to a flat Python script does not support top-level await. If you have
top-level await in your notebook, you can still execute the notebook as a
script with `python notebook.py`.
```

## Export to markdown

Export to markdown notebook in top to bottom order, so the cells are in the
order as they appear in the notebook.

```bash
marimo export md notebook.py -o notebook.md
```

This can be useful to plug into other tools that read markdown, such as [Quarto](https://quarto.org/) or [MyST](https://myst-parser.readthedocs.io/).

You can also convert the markdown back to a marimo notebook:

```bash
marimo convert notebook.md > notebook.py
```

## Export to Jupyter notebook

Export to Jupyter notebook in topological order, so the cells adhere to
their dependency graph.

```bash
marimo export ipynb notebook.py -o notebook.ipynb
```
