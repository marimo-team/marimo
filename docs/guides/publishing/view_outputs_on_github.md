# View Outputs on GitHub

marimo notebooks are stored as pure Python files, in order to
work with Git versioning and the broader Python ecosystem. However, this means
that unlike Jupyter notebooks, by default you cannot see marimo notebook
outputs on GitHub.

If you would like to make outputs viewable on GitHub, you can configure
any given marimo notebook to automatically snapshot its outputs to an
`ipynb` file. The snapshot will be saved to a `__marimo__` directory
in the same folder where the notebook lives, which you can then
push to GitHub.

Enable snapshotting in the notebook settings menu, using the gear icon in the
top right of any notebook.
