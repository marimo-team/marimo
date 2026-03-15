# GitHub

marimo makes it very easy to share links to executable notebooks from notebooks
hosted on GitHub. 

- [Share molab links](../molab.md#preview-notebooks-from-github) to obtain interactive previews of notebooks hosted on GitHub, no login required
- Publish notebooks to [GitHub Pages](#publish-to-github-pages)

## Share previews of notebooks hosted on GitHub

You can share previews of any marimo notebook hosted on GitHub using
[molab](../molab.md); these previews are publicly viewable, no login required.
Simply replace `github.com` in your notebook's GitHub URL with
`molab.marimo.io/github` to create a shareable preview link. For example:

```
https://github.com/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py
```

becomes

```
https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py
```

Previews are **static** by default. To make them **interactive**, append
`/wasm` to the URL (the notebook must be [WebAssembly-compatible](../wasm.md)).

To include outputs in static previews, commit the notebook's session JSON file (in the `__marimo__/session/` directory alongside the notebook). Generate it with:

```bash
marimo export session notebook.py
```

You can also share links using our open-in-molab badge. For example:

```markdown
[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm)
```

becomes

[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm)


Visit [molab.marimo.io/github](https://molab.marimo.io/github) to automatically
generate preview URLs and badges from GitHub links.

For full details on previewing, embedding, and sharing, see the [molab guide](../molab.md#preview-notebooks-from-github).

## Export to ipynb to view on GitHub

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

## Publish to GitHub Pages

> For a simpler solution, use [molab's built in GitHub previewer](../molab.md#preview-notebooks-from-github)

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
