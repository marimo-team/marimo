# WASM notebooks

It's possible to run marimo **entirely in the browser** -- no backend required! marimo
notebooks that run entirely in the browser are called **WebAssembly
notebooks**, or **WASM notebooks** for short.

In contrast to marimo notebooks that you create with the CLI, WASM notebooks
run without a web server and Python process; instead, the web browser executes
your Python code. For this reason, WASM makes it extremely easy to
share marimo notebooks, and makes it possible to tinker with notebooks without
having to install Python on your machine.

**Try a WASM notebook today!** Just navigate to
[https://marimo.new](https://marimo.new).

```{admonition} WASM?
:class: note

marimo-in-the-browser is powered by a technology called
[WebAssembly](https://webassembly.org/), or "WASM" for short. Hence the
name "WASM notebook".
```

```{admonition} When should I use WASM notebooks?
:class: note

WASM notebooks are excellent for sharing your work, quickly experimenting with
code and models, doing lightweight data exploration, authoring blog posts,
tutorials, and educational materials, and even building tools. They are
not well-suited for notebooks that do heavy computation.
```

```{admonition} Issues?
:class: warning

WASM notebooks are a new feature. If you run into
problems, please open a [GitHub issue](https://github.com/marimo-team/marimo/issues).
```

## Creating and sharing WASM notebooks

WASM notebooks run at [marimo.app](https://marimo.app).

### Creating new notebooks

To create a new WASM notebook, just visit
[marimo.new](https://marimo.new).

Think of [marimo.new](https://marimo.new) as your own personal
scratchpad for experimenting with code, data, and models and for prototyping
tools, available to you at all times and on all devices.

```{admonition} Saving WASM notebooks
:class: tip

When you save a WASM notebook, a copy of your code is saved to your
web browser's local storage. When you return to [marimo.app](https://marimo.app),
the last notebook you worked on will be re-opened.
```

### Creating shareable permalinks

At [marimo.app](https://marimo.app), save your notebook and then click the
`Create permalink` button to generate a shareable permalink to your
notebook.

Please be aware that marimo permalinks are publicly accessible.

### Creating WASM notebooks from local notebooks

In the marimo editor's notebook action menu, use `Share > Create WebAssembly
link` to get a `marimo.app/...` URL representing your notebook:

<div align="center">
<figure>
<img src="/_static/share-wasm-link.gif"/>
</figure>
</div>

WASM notebooks come with common Python packages installed, but you may need to
[install additional packages using micropip](#installing-packages).

The obtained URL encodes your notebook code as a parameter, so it can be
quite long. If you want a URL that's easier to share, you can [create a
shareable permalink](#creating-shareable-permalinks).

## Installing packages

WASM notebooks come with many packages pre-installed, including
NumPy, SciPy, scikit-learn, pandas, and matplotlib; see [Pyodide's
documentation](https://pyodide.org/en/stable/usage/packages-in-pyodide.html)
for a full list.

To install other packages, use `micropip`:

In one cell, import micropip:

```python
import micropip
```

In the next one, install packages:

```python
await micropip.install("plotly")
import plotly
```

**Try it!** A WASM notebook is embedded below. Try installing a package.

<iframe src="https://marimo.app/l/wvz76s?embed=true" width=800 height=300>
</iframe>

## Configuration

Your `marimo.app` URLs can be configured using the following parameters.

### Read-only mode

To view a notebook in read-only mode, with
code cells locked, append `&mode=read` to your URL's list of query parameters
(or `?mode=read` if your URL doesn't have a query string).

Example:

- `https://marimo.app/l/83qamt?mode=read`

### Embed

To hide the `marimo.app` header, append `&embed=true` to your URL's list of query
parameters (or `?embed=true` if your URL doesn't have a query string).

Example:

- `https://marimo.app/l/83qamt?embed=true`
- `https://marimo.app/l/83qamt?mode=read&embed=true`

See the [section on embedding](#embedding) for examples of how to embed marimo
notebooks in your own webpages.

### Excluding code

By default, WASM notebooks expose your Python code to viewers. If you've
enabled read-only mode, you can exclude code with
`&include-code=false`.

A sufficiently determined user would still be able
to obtain your code, so **don't** think of this as a security feature; instead,
think of it as an aesthetic or practical choice.

## Embedding

WASM notebooks can be embedded into other webpages using the HTML `<iframe>`
tag.

### Embedding an blank notebook

Use the following snippet to embed a blank marimo notebook into your web page,
providing your users with an interactive code playground.

```html
<iframe
  src="https://marimo.app/l/aojjhb?embed=true"
  width="800"
  height="300"
></iframe>
```

<iframe src="https://marimo.app/l/aojjhb?embed=true" width="800" height="300"></iframe>

### Embedding an existing notebook

To embed existing marimo notebooks into a webpage, first, [obtain a
URL to your notebook](#creating-and-sharing-wasm-notebooks), then put it in an iframe.

```html
<iframe
  src="https://marimo.app/l/c7h6pz?embed=true"
  width="800"
  height="300"
></iframe>
```

<iframe src="https://marimo.app/l/c7h6pz?embed=true" width="800" height="600"></iframe>

After obtaining a URL to your
notebook,

### Embedding an existing notebook in read-only mode

You can optionally render embedded notebooks in read-only mode by appending
`&mode=read` to your URL.

```html
<iframe
  src="https://marimo.app/l/c7h6pz?mode=read&embed=true"
  width="800"
  height="300"
></iframe>
```

<iframe src="https://marimo.app/l/c7h6pz?mode=read&embed=true" width="800" height="600"></iframe>

## Limitations

While WASM notebooks let you get up and running with marimo instantly, they
have some limitations.

**Packages.** Not all packages are available in WASM notebooks; see [Pyodide's
documentation on supported packages.](https://pyodide.org/en/stable/usage/packages-in-pyodide.html)

**PDB.** PDB is not currently supported. This may be fixed in the future.

**Threading and multi-processing.** WASM notebooks do not support multithreading
and multiprocessing. [This may be fixed in the future](https://github.com/pyodide/pyodide/issues/237).

## Browser support

WASM notebooks are supported in the latest versions of Chrome, Firefox, Edge, and Safari.

Chrome is the recommended browser for WASM notebooks as it seems to have the
best performance and compatibility.
