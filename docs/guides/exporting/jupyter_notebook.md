# Jupyter notebook

Export marimo notebooks to Jupyter `.ipynb` format.

## Export from the command line

Export to Jupyter notebook in topological order, so the cells adhere to
their dependency graph.

```bash
marimo export ipynb notebook.py -o notebook.ipynb
```
