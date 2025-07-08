# WebAssembly Notebooks

marimo lets you execute notebooks _entirely in the browser_,
without a backend executing Python. marimo notebooks that
run entirely in the browser are called WebAssembly notebooks, or WASM notebooks
for short.

!!! tip "Try our online playground"

    To create your first WASM notebook, try our online playground
    at [marimo.new](https://marimo.new). Read the [playground
    docs](publishing/playground.md) to learn more.

WASM notebooks have three benefits compared to notebooks hosted using a
traditional client-server model. WASM notebooks:

1. eliminate the need to install Python, making scientific computing accessible;
2. eliminate the cost and complexity of deploying backend infrastructure, making it easy to share notebooks;
3. eliminate network requests to a remote Python runner, making development feel snappy.

!!! question "When should I use WASM notebooks?"

    WASM notebooks are excellent for sharing your work, quickly experimenting
    with code and models, doing lightweight data exploration, authoring blog
    posts, tutorials, and educational materials, and even building tools. For
    notebooks that do heavy computation, [use marimo
    locally](../getting_started/index.md) or on a backend.

**Try it!** Try editing the below notebook (your browser, not a backend server, is executing it!)

<iframe src="https://marimo.app/l/upciwv?embed=true" width="100%" height=400 frameBorder="0"></iframe>

_This feature is powered by [Pyodide](https://pyodide.org), a port
of Python to WebAssembly that enables browsers to run Python code._

## Creating WASM notebooks

marimo provides three ways to create and share WASM notebooks:

1. [Export to WASM HTML](exporting.md#export-to-wasm-powered-html),
   which you can host on GitHub Pages or self-host. This is great for
   publishing companion notebooks for research papers that are automatically
   updated on Git push, or for embedding interactive notebooks as part of other
   websites.
2. The [online playground](publishing/playground.md), which lets you
   create one-off notebooks and share via links, no login required. The
   playground is also great for embedding editable notebooks in
   documentation.
3. The [Community Cloud](publishing/community_cloud/index.md), which
   lets you save a collection of notebook to a workspace (for free!) and share
   publicly or privately with sensible URLs.

### From GitHub

marimo provides three ways to share notebooks stored on GitHub as WASM notebooks:

1. Automatically publish to GitHub Pages on git push with [our GitHub action](publishing/github_pages.md).
2. Load a notebook by URL into the online playground (New > Open from URL ...)
3. Load a notebook from GitHub in the [Community Cloud](publishing/community_cloud/index.md).

## Packages

!!! tip "Rendering performance"

    To make sure markdown and other elements render quickly: make sure to put
    `import marimo as mo` in its own cell, with no other lines of code.

WASM notebooks come with many packages pre-installed, including
NumPy, SciPy, scikit-learn, pandas, and matplotlib; see [Pyodide's
documentation](https://pyodide.org/en/stable/usage/packages-in-pyodide.html)
for a full list.

If you attempt to import a package that is not installed, marimo will
attempt to automatically install it for you. To manually install packages, use
[`micropip`](https://micropip.pyodide.org/en/stable/project/usage.html):

In one cell, import micropip:

```python
import micropip
```

In the next cell, install packages:

```python
await micropip.install("plotly")
import plotly
```

### Supported packages

All packages with pure Python wheels on PyPI are supported, as well as
additional packages like NumPy, SciPy, scikit-learn, duckdb, polars, and more.
For a full list of supported packages, see [Pyodide's
documentation on supported packages.](https://pyodide.org/en/stable/usage/packages-in-pyodide.html)

If you want a package to be supported, consider [filing an issue](https://github.com/pyodide/pyodide/issues/new?assignees=&labels=new+package+request&projects=&template=package_request.md&title=).

## Including data

**For notebooks exported to WASM HTML.**
To include data files in notebooks [exported to WASM
HTML](exporting.md#export-to-wasm-powered-html), place them
in a `public/` folder in the same directory as your notebook. When you
export to WASM HTML, the public folder will be copied to the export directory.

In order to access data both locally and when an exported notebook runs via
WebAssembly (e.g., hosted on GitHub Pages), use
[`mo.notebook_location()`][marimo.notebook_location] to construct the path to
your data:

```python
import polars as pl

path_to_csv = mo.notebook_location() / "public" / "data.csv"
df = pl.read_csv(str(path_to_csv))
df.head()
```

**Fetching data files from the web.**
Instead of bundling data files with your notebook, you can host data files on
the web and fetch them in your notebook. Depending on where your files are
hosted, you may need to use a CORS Proxy; see the [Pyodide
documentation](https://pyodide.org/en/stable/usage/loading-packages.html#installing-wheels-from-arbitrary-urls)
for more details.

**Playground notebooks.** When opening a playground
notebook from GitHub, all the files in the GitHub repo are made available to
your notebook. See the [Playground
Guide](publishing/playground.md#including-data-files) for more info.

**Community Cloud notebooks.** Our free [Community
Cloud](publishing/community_cloud/index.md) lets you upload a limited
amount of data, and also lets you sync notebooks (and their data) from GitHub.

## Limitations

While WASM notebooks let you share marimo notebooks seamlessly, they have some
limitations.

**Packages.** Many but not all packages are supported. All packages with pure
Python wheels on PyPI are supported, as well as additional packages like NumPy,
SciPy, scikit-learn, duckdb, polars, and more. For a full list of supported
packages, see [Pyodide's documentation on supported
packages.](https://pyodide.org/en/stable/usage/packages-in-pyodide.html)

If you want a package to be supported, consider [filing an
issue](https://github.com/pyodide/pyodide/issues/new?assignees=&labels=new+package+request&projects=&template=package_request.md&title=).

**PDB.** PDB is not currently supported.

**Threading and multi-processing.** WASM notebooks do not support multithreading
and multiprocessing. [This may be fixed in the future](https://github.com/pyodide/pyodide/issues/237).

**Memory.** WASM notebooks have a memory limit of 2GB; this may be increased
in the future. If memory consumption is an issue, try offloading memory-intensive
computations to hosted APIs or precomputing expensive operations.

## Browser support

WASM notebooks are supported in the latest versions of Chrome, Firefox, Edge, and Safari.

Chrome is the recommended browser for WASM notebooks as it seems to have the
best performance and compatibility.
