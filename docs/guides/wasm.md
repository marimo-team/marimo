# WASM Notebooks

It's possible to run marimo **entirely in the browser** -- no backend required! marimo
notebooks that run entirely in the browser are called **WebAssembly
notebooks**, or **WASM notebooks** for short.

In contrast to marimo notebooks that you create with the CLI, WASM notebooks
run without a web server and Python process; instead, the web browser executes
your Python code. For this reason, WASM makes it extremely easy to
share marimo notebooks, and make it possible to tinker with notebooks without
having to install Python on your machine.

```{admonition} WASM?
:class: note

marimo-in-the-browser is powered by a technology called
[WebAssembly](https://webassembly.org/), or "WASM" for short. Hence the
name "WASM notebook".
```

**You can try a WASM notebook today!** Just navigate to
[https://marimo.new](https://marimo.new).

**Common use cases.** XXX bullets

XXX TODO

- marimo.new: playground
- marimo.app: opens whatever you were last working on (tutorials)
- read mode (?mode=read) (XXX short links?)

- running as an app

- packages: preloaded, micropip

- use cases
  - embedding
  - embedding a REPL in a webpage (iframe)
  - embedding a notebook in a webpage
  - embedding an app in a webpage
  - sharing
  - playground

## Creating and sharing WASM notebooks

XXX TODO

- go from local -> shareable with Get WebAssembly Link

- from `marimo.new` - scratch pad / blank notebook
- from `marimo.app` : load your most recent notebook
  - from `Get short link`

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

## Limitations

WASM lets you get up and running with marimo instantly, and makes sharing
marimo notebooks frictionless. That said, WASM notebooks do have some
limitations.

**Packages.** Not all packages are available in WASM notebooks; see [Pyodide's
documentation](https://pyodide.org/en/stable/usage/packages-in-pyodide.html),
to learn more about which packages are supported.

**Threading and multi-processing.** WASM notebooks do not support multithreading
and multiprocessing. This may change in the future.

**Code completion.** Code completion and docstring hints are not
currently supported. This restriction will be removed in the future.

In general, WASM notebooks are not well-suited for notebooks that do heavy computation
or rely on packages not supported by Pyodide. In contrast, they are excellent
for sharing your work, quickly experimenting with code and models, doing
lightweight data analysis, authoring blog posts, tutorials, and educational
articles, and even building internal tools.


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
	src="https://marimo.app/?slug=c7h6pz&embed=true"
	width="800"
	height="300"
></iframe>
```

<iframe src="https://marimo.app/?slug=c7h6pz&embed=true" width="800" height="600"></iframe>

After obtaining a URL to your
notebook,

### Embedding an existing notebook in read-only mode

You can optionally render embedded notebooks in read-only mode by appending
`&mode=read` to your URL.

```html
<iframe
	src="https://marimo.app/?slug=c7h6pz&mode=read"
	width="800"
	height="300"
></iframe>
```

<iframe src="https://marimo.app/?slug=c7h6pz&mode=read&embed=true" width="800" height="600"></iframe>
