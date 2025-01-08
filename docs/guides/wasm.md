# WebAssembly Notebooks

marimo makes it possible to execute notebooks _entirely in the browser_,
without a backend to execute the notebook's Python code. marimo notebooks that
run entirely in the browser are called WebAssembly notebooks, or WASM notebooks
for short.

!!! tip "Try our online playground"

    To create your first WASM notebook, try our online playground
    at [marimo.new](https://marimo.new). Read the [playground
    docs](../guides/publishing/playground.md) to learn more.

WASM notebooks have three main benefits compared to notebooks hosted using a
traditional client-server model. WASM notebooks:

1. eliminate the need to install Python, making scientific computing accessible;
2. eliminate the cost and complexity of deploying backend infrastructure, making it easy to share notebooks;
3. eliminate network requests to a remote Python runner, making development feel snappy.

!!! question "When should I use WASM notebooks?"

    WASM notebooks are excellent for sharing your work, quickly experimenting
    with code and models, doing lightweight data exploration, authoring blog
    posts, tutorials, and educational materials, and even building tools. For
    notebooks that do heavy computation, [run notebooks
    locally](http://127.0.0.1:8000/getting_started/) or on a backend.

**Try it!** Try editing the below notebook (your browser, not a backend server, is executing it!)

<iframe src="https://marimo.app/l/upciwv?embed=true" width="100%" height=400 frameBorder="0"></iframe>

_This feature is powered by [Pyodide](https://pyodide.org), a port
of Python to WebAssembly that enables browsers to run Python code._

## Creating WASM notebooks

marimo provides three ways to create and share WASM notebooks:

1. The [online playground](../guides/publishing/playground.md), which lets you
   create one-off notebooks and share via links, no login required. The
   playground is also great for embedding editable notebooks in
   documentation.
2. The [Community Cloud](../guides/publishing/community_cloud/index.md), which
   lets you save a collection of notebook to a workspace (for free!) and share
   publicly or privately with sensible URLs.
3. Exporting notebooks as [WASM-powered HTML](../guides/exporting/#export-to-wasm-powered-html),
   which you can host on GitHub Pages or self-host. This is great for
   publishing companion notebooks for research papers that are automatically
   updated on Git push, or for embedding interactive notebooks as part of other
   websites.

## Installing packages

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

XXX

## Creating notebooks from GitHub

XXX

## Limitations

While WASM notebooks let you get up and running with marimo instantly, and
make it extremely easy to share, they have some limitations.

**PDB.** PDB is not currently supported. This may be fixed in the future.

**Threading and multi-processing.** WASM notebooks do not support multithreading
and multiprocessing. [This may be fixed in the future](https://github.com/pyodide/pyodide/issues/237).

**Memory.** WASM notebooks have a memory limit of 2GB; this may be increased
in the future. If memory consumption is an issue, try offloading memory-intensive
computations to hosted APIs or precomputing expensive operations.

## Browser support

WASM notebooks are supported in the latest versions of Chrome, Firefox, Edge, and Safari.

Chrome is the recommended browser for WASM notebooks as it seems to have the
best performance and compatibility.
