# Jupyter notebook

Export marimo notebooks to Jupyter `.ipynb` format. This lets you
go from marimo into the vast Jupyter export ecosystem, including tools
like `nbconvert`, Quarto, JupyterBook, and more.

## Export from the marimo editor

You can configure individual notebooks to automatically
save as ipynb through the notebook menu. These automatic snapshots are
saved to a folder called `__marimo__` in the notebook directory.

<div align="center">
<figure>
<img src="/_static/docs-jupyter-autoexport.png" width="75%"/>
<figcaption>Download as static HTML.</figcaption>
</figure>
</div>

## Export from the command line

Export to Jupyter notebook in topological order, so the notebook
can be run from top to bottom:

```bash
marimo export ipynb notebook.py -o notebook.ipynb
```


Export with cells in the same order as the marimo notebook:

```bash
marimo export ipynb notebook.py -o notebook.ipynb --sort=top-down
```

See all options:

```bash
marimo export ipynb notebook.py -o notebook.ipynb --sort=top-down
```


## Convert back to a marimo notebook

You can also convert a Jupyter notebook back to a marimo notebook:

```bash
marimo convert notebook.ipynb -o notebook.py
```
