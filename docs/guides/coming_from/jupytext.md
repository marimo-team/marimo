# Coming from Jupytext

If you're familiar with Jupytext, you'll find that marimo offers similar functionality for working with notebooks as python files, but without the need for additional setup or synchronization issues. Here's a comparison to help you transition smoothly.

## Notebook Format

- **Jupytext**: Jupytext uses comments or special markers to define cell types in notebooks.
- **marimo**: Notebooks are pure Python (`.py`) files by default, using standard Python syntax, such as decorators and functions to define cells.

## Converting Jupyter Notebooks (ipynb)

### From `.ipynb`

- **Jupytext**: `jupytext --to py notebook.ipynb`
- **marimo**: `marimo convert notebook.ipynb > notebook.py`

### To `.ipynb`

- **Jupytext**: `jupytext --to notebook.ipynb notebook.py`
- **marimo**: `marimo export ipynb notebook.py > notebook.ipynb`

## Editing Notebooks

- **Jupytext**: Requires synchronization between `.ipynb` and `.py` files.
- **marimo**: Edit marimo notebooks files directly in the marimo editor (`marimo edit notebook.py`) and changes are read from and written to the same file.

## Executing Notebooks

- **Jupytext**: Use Jupyter or Papermill to execute notebooks.
- **marimo**: Run notebooks as scripts (`python notebook.py`) or as apps (`marimo run notebook.py`).

## Version Control

- **Jupytext**: Pair and synchronize notebooks (ipynb) with text representations for smaller git diffs.
- **marimo**: Notebooks are already in `.py` format, making them git-friendly by default. They can be linted and formatted like any other Python file.

## Markdown and Code Cells

- **Jupytext**: Uses special markers or formats to distinguish cell types. Magical syntax is required.
- **marimo**: Uses `mo.md("...")` for Markdown content. Regular Python code doesn't need special markers.

## Interactive Elements

- **Jupytext**: Relies on Jupyter widgets, requires additional setup.
- **marimo**: Built-in `mo.ui` module for interactive elements, automatically synchronized with Python.

## Reactive Execution

- **Jupytext**: Not available; cells execute in order from top to bottom.
- **marimo**: Automatic reactive execution based on cell dependencies.

## Deployment

- **Jupytext**: Requires additional tools for deployment.
- **marimo**: Can be deployed as interactive web apps with `marimo run`.
