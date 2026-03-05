# GitHub

marimo makes it very easy to share links to executable notebooks from notebooks
hosted on GitHub. Unlike Google Colab, marimo also automatically synchronizes
data stored in your GitHub repo to the notebook's filesystem, making it
easy to bundle data with your notebooks.

/// tip | Recommended: share with molab
The easiest way to share notebooks from GitHub is with [molab](../molab.md). Just push your notebook to GitHub and [share a molab link](https://molab.marimo.io/github) — viewers can interact with and fork your notebook instantly.
///

- [Share molab links](https://molab.marimo.io/github) to notebooks hosted on GitHub
- Publish notebooks to [GitHub Pages](#publish-to-github-pages)
- Edit notebooks on the [marimo playground](https://marimo.app), with public link-based sharing
  (no login required!)

## View outputs on GitHub

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

## Publish to GitHub Pages

You can publish executable notebooks to [GitHub Pages](https://pages.github.com/)
for free, after exporting your notebook to a WebAssembly notebook.

### Export to WASM-powered HTML

Export your notebook to a self-contained HTML file that runs using [WebAssembly](../wasm.md):

/// tab | Export as a readonly app

```bash
marimo export html-wasm notebook.py -o output_dir --mode run
```

///

/// tab | Export as an editable notebook

```bash
marimo export html-wasm notebook.py -o output_dir --mode edit
```

///

See our [exporting guide](../exporting/webassembly_html.md) for
the full documentation.

### Publish using GitHub Actions

/// tip | Template repository

Fork our [template repository](https://github.com/marimo-team/marimo-gh-pages-template) for deploying multiple notebooks to GitHub Pages. Once you have forked the repository, add your notebooks to the `notebooks` or `apps` directories,
for editable or readonly respectively.
///

Publish to GitHub Pages using the following GitHub Actions workflow,
which will republish your notebook on git push.

```yaml
jobs:
    build:
        runs-on: ubuntu-latest

        steps:
            # ... checkout and install dependencies

            - name: 📄 Export notebook
              run: |
                  marimo export html-wasm notebook.py -o path/to/output --mode run

            - name: 📦 Upload Pages Artifact
              uses: actions/upload-pages-artifact@v3
              with:
                  path: path/to/output

    deploy:
        needs: build
        runs-on: ubuntu-latest
        environment:
            name: github-pages
            url: ${{ steps.deployment.outputs.page_url }}

        permissions:
            pages: write
            id-token: write

        steps:
            - name: 🌐 Deploy to GitHub Pages
              id: deployment
              uses: actions/deploy-pages@v4
              with:
                  artifact_name: github-pages
```

### Publish manually

You can also publish an exported notebook manually through your repository
settings. Read [GitHub's documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) to learn more.

Make sure to [include a `.nojekyll`
file](https://github.blog/news-insights/bypassing-jekyll-on-github-pages/) in
root folder from which your site is built to prevent GitHub from interfering
with your site.
