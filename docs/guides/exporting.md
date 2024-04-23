# Exporting

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

Export the notebook to a flat Python script at the command-line.
This exports the notebook in topological order, so the cells adhere to their dependency graph.

```bash
marimo export script notebook.py -o notebook.script.py
```

```{admonition} Top-level await not supported
:class: warning

Exporting to a flat Python script does not support top-level await.
If you have top-level await in your notebook, you can still execute the notebook as a script with `python notebook.py`.
```
