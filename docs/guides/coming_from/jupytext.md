# Coming from Jupytext

If you're familiar with Jupytext, you'll find that marimo offers similar
functionality for working with notebooks as Python files, but without the need
for additional setup or synchronization issues because marimo notebooks
are stored as `.py` files by default. However, Jupytext works with IPython
notebooks, whereas marimo works with marimo notebooks, which are not based
on IPython/Jupyter. Here's a comparison to help you transition smoothly.

!!! tip "marimo also has a markdown fileformat"
    Learn more about it with `marimo tutorials markdown-format`.

## Notebook Format

| Jupytext | marimo |
|----------|--------|
| Jupytext uses comments or special markers to define cell types in notebooks. | Notebooks are pure Python (`.py`) files by default, using standard Python syntax, such as decorators and functions, to define cells. In markdown form (`.md`), marimo has no special syntax, meaning your notebook will render well in locations like Github. |

## Converting Jupyter notebooks

### From `.ipynb`

| Jupytext | marimo |
|----------|--------|
| `jupytext --to py notebook.ipynb` | `marimo convert notebook.ipynb > notebook.py` |

!!! tip "From py:percent notebooks to marimo notebooks"
    If you have a Python file encoded in the [py:percent](https://jupytext.readthedocs.io/en/latest/#text-notebooks)
    format, you can convert it to a marimo notebook in two steps:

    ```
    jupytext --to notebook.ipynb percent_notebook.py
    marimo convert notebook.ipynb > marimo_notebook.py
    ```

### To `.ipynb`

| Jupytext | marimo |
|----------|--------|
| `jupytext --to notebook.ipynb notebook.py` | `marimo export ipynb notebook.py > notebook.ipynb` |

## Editing Notebooks

| Jupytext | marimo |
|----------|--------|
| Requires synchronization between `.ipynb` and `.py` files. | Edit marimo notebooks files directly in the marimo editor (`marimo edit notebook.py`), and changes are read from and written to the same file. |

## Executing Notebooks

| Jupytext | marimo |
|----------|--------|
| Use Jupyter to edit notebooks interactively, or Papermill to execute notebooks from the command line. | In addition to running notebooks interactively (`marimo notebook.py`), you can run notebooks as scripts (`python notebook.py`) or as apps (`marimo run notebook.py`), passing values to them with marimo's built-in support for [CLI args](../../api/cli_args.md). |

## Version Control

| Jupytext | marimo |
|----------|--------|
| Jupyter notebooks are stored as JSON by default, making them difficult to meaningfully version with git. Use Jupytext to pair and synchronize jupyter notebooks with text representations for smaller git diffs. | Notebooks are already in `.py` format, making them git-friendly by default. Small changes to the notebook are guaranteed to yield small diffs. |

## Markdown and Code Cells

| Jupytext | marimo |
|----------|--------|
| Uses special markers or formats to distinguish cell types. Magical syntax is required. | Uses `mo.md("...")` for Markdown content, and interpolate Python values with `mo.md(f"...")`; no magical syntax. |

## Deployment

| Jupytext | marimo |
|----------|--------|
| Requires migrating to other libraries like Voila or Streamlit for deployment. | Can be deployed as interactive web apps with `marimo run`. |
