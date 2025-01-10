# Publish to GitHub Pages

You can publish executable notebooks to [GitHub Pages](https://pages.github.com/)
for free, after exporting your notebook to a WebAssembly notebook.

## Export to WASM-powered HTML

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

See our [exporting guide](../exporting.md#export-to-wasm-powered-html) for
the full documentation.

## Publish using GitHub Actions

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

## Publish manually

You can also publish an exported notebook manually through your repository
settings. Read [GitHub's documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) to learn more.

Make sure to [include a `.nojekyll`
file](https://github.blog/news-insights/bypassing-jekyll-on-github-pages/) in
root folder from which your site is built to prevent GitHub from interfering
with your site.
