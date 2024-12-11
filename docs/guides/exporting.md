# Exporting to HTML and other formats

Export marimo notebooks to other file formats at the command line using

```bash
marimo export
```

## Export to static HTML

### Export from a running notebook

Export the current view your notebook to static HTML via the notebook
menu:

<div align="center">
<figure>
<img src="/_static/docs-html-export.png"/>
<figcaption>Download as static HTML.</figcaption>
</figure>
</div>

Additionally, you can configure individual notebooks to automatically
save as HTML through the notebook menu. These automatic snapshots are
saved to a folder called `__marimo__` in the notebook directory.

### Export from the command line

Export to HTML at the command line:

```bash
marimo export html notebook.py -o notebook.html
```

or watch the notebook for changes and automatically export to HTML:

```bash
marimo export html notebook.py -o notebook.html --watch
```

When you export from the command line, marimo runs your notebook to produce
its visual outputs before saving as HTML.

```{admonition} Note
:class: note

If any cells error during the export process, the status code will be non-zero. However, the export result may still be generated, with the error included in the output.
Errors can be ignored by appending `|| true` to the command, e.g. `marimo export html notebook.py || true`.
```

## Export to a Python script

Export to a flat Python script in topological order, so the cells adhere to
their dependency graph.

```bash
marimo export script notebook.py -o notebook.script.py
```

```{admonition} Top-level await not supported
:class: warning

Exporting to a flat Python script does not support top-level await. If you have
top-level await in your notebook, you can still execute the notebook as a
script with `python notebook.py`.
```

## Export to markdown

Export to markdown notebook in top to bottom order, so the cells are in the
order as they appear in the notebook.

```bash
marimo export md notebook.py -o notebook.md
```

This can be useful to plug into other tools that read markdown, such as [Quarto](https://quarto.org/) or [MyST](https://myst-parser.readthedocs.io/).

You can also convert the markdown back to a marimo notebook:

```bash
marimo convert notebook.md > notebook.py
```

## Export to Jupyter notebook

Export to Jupyter notebook in topological order, so the cells adhere to
their dependency graph.

```bash
marimo export ipynb notebook.py -o notebook.ipynb
```

## Exporting to PDF, slides, or rst

If you export to a Jupyter notebook, you can leverage various Jupyter ecosystem tools. For PDFs, you will
need to have [Pandoc](https://nbconvert.readthedocs.io/en/latest/install.html#installing-pandoc) and [Tex](https://nbconvert.readthedocs.io/en/latest/install.html#installing-tex) installed. The examples below use `uvx`, which you can obtain by [installing `uv`](https://docs.astral.sh/uv/getting-started/installation/).

```bash
NOTEBOOK=notebook.ipynb

# Convert to PDF using nbconvert
uvx --with nbconvert --from jupyter-core jupyter nbconvert --to pdf $NOTEBOOK

# Convert to web PDF
uvx --with "nbconvert[webpdf]" --from jupyter-core jupyter nbconvert --to webpdf $NOTEBOOK --allow-chromium-download

# Convert to slides
uvx --with nbconvert --from jupyter-core jupyter nbconvert --to slides $NOTEBOOK

# Convert to rst with nbconvert
uvx --with nbconvert --from jupyter-core jupyter nbconvert --to rst $NOTEBOOK

# Generate PNG/PDF of specific cells using nbconvert
uvx --with nbconvert --with jupyter --from jupyter-core jupyter nbconvert --to pdf --execute --stdout $NOTEBOOK \
  --TemplateExporter.exclude_input=True

# Use nbconvert programmatically for more control
uv run --with nbconvert python -c "
from nbconvert import PDFExporter
import nbformat
nb = nbformat.read('$NOTEBOOK', as_version=4)
pdf_exporter = PDFExporter()
pdf_data, resources = pdf_exporter.from_notebook_node(nb)
with open('notebook.pdf', 'wb') as f:
    f.write(pdf_data)
"
```

You can also use other tools that work with Jupyter notebooks:

- [Quarto](https://quarto.org) - Create beautiful documents, websites, presentations
- [nbgrader](https://nbgrader.readthedocs.io/) - Grade notebook assignments

## 🏝️ Embed marimo outputs in HTML using Islands

```{admonition} Preview
:class: note

Islands are an early feature. While the API likely won't change, there are some improvements we'd like to make before we consider them stable.
Please let us know on [GitHub](https://github.com/marimo-team/marimo/issues) if you run into any issues or have any feedback!
```

marimo islands are a way to embed marimo outputs and/or python code in your HTML that will become interactive when the page is loaded. This is useful for creating interactive blog posts, tutorials, and educational materials, all powered by marimo's reactive runtime.

Check out an [example island-powered document](./island_example.md).

### Islands in action

```{admonition} Advanced topic!
:class: warning

Islands are an advanced concept that is meant to be a building block for creating integrations with existing tools such as static site generators or documentation tools.
```

In order to use marimo islands, you need to import the necessary JS/CSS headers in your HTML file, and use our custom HTML tags to define the islands.

```html
<head>
  <!-- marimo js/ccs -->
  <script type="module" src="https://cdn.jsdelivr.net/npm/@marimo-team/islands@<version>/dist/main.js"></script>
  <link
    href="https://cdn.jsdelivr.net/npm/@marimo-team/islands@<version>/dist/style.css"
    rel="stylesheet"
    crossorigin="anonymous"
  />
  <!-- fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Fira+Mono:wght@400;500;700&amp;family=Lora&amp;family=PT+Sans:wght@400;700&amp;display=swap"
    rel="stylesheet"
  />
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css"
    integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww"
    crossorigin="anonymous"
  />
</head>

<body>
  <marimo-island data-app-id="main" data-cell-id="MJUe" data-reactive="true">
    <marimo-cell-output>
      <span class="markdown">
        <span class="paragraph">Hello, islands!</span>
      </span>
    </marimo-cell-output>
    <marimo-cell-code hidden>mo.md('Hello islands 🏝️!')</marimo-cell-code>
  </marimo-island>
</body>
```

### Generating islands

While you can generate the HTML code for islands yourself, it it recommend to use our `MarimoIslandGenerator` class to generate the HTML code for you.

```{eval-rst}
.. autoclass:: marimo.MarimoIslandGenerator
  :members:

  .. autoclasstoc::
```
