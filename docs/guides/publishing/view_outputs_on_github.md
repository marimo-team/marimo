# View Outputs on GitHub

marimo notebooks are stored as pure Python files, which works well with Git
versioning and the broader Python ecosystem. However, this means you cannot
preview outputs directly on GitHub like you can with Jupyter notebooks.

To make outputs viewable on GitHub, you can configure marimo to automatically
snapshot outputs to an `ipynb` file. We treat the ipynb as an artifact that
combines your source code with rendered outputs. The snapshot is saved to a
`__marimo__` directory alongside your notebook, which you can commit and push
to GitHub.

Enable snapshotting in the notebook settings menu via the gear icon in the top
right corner:

<picture>
  <source srcset="/_static/docs-notebook-settings-snapshotting.webp" type="image/webp">
  <img src="/_static/docs-notebook-settings-snapshotting.jpg" alt="Notebook settings dialog showing the Exporting outputs section with HTML and ipynb checkboxes" style="max-width: 700px; width: 100%;" />
</picture>

This feature requires `nbformat`. marimo will prompt to install it if missing, or you can add it to your environment with `pip install nbformat`.
