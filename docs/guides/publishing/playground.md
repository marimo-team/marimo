# Online playground

Our [online playground](https://marimo.app) lets you
create and share marimo notebooks for free, without creating an account.

Playground notebooks are great for embedding in other web pages — all the
notebooks embedding in marimo's own docs are playground notebooks. They
are also great for sharing via links.

**Try our playground!** Just navigate to
[https://marimo.new](https://marimo.new).

!!! note "WebAssembly notebooks only"

    Currently, the online playground only allows the creation of [WebAssembly
    notebooks](../wasm.md). These are easy to share and embed in other
    web pages, but have some limitations in packages and performance.

_The notebook embedded below is a playground notebook!_

<iframe src="https://marimo.app/l/upciwv?embed=true" width="100%" height=400 frameBorder="0"></iframe>

## Creating and sharing WASM notebooks

WASM notebooks run at [marimo.app](https://marimo.app).

### New notebooks

To create a new playground notebook, visit <https://marimo.new>.

Think of [marimo.new](https://marimo.new) as a
scratchpad for experimenting with code, data, and models and for prototyping
tools, available to you at all times and on all devices.

!!! tip "Saving playground notebooks"

    When you save a WASM notebook, a copy of your code is saved to your
    web browser's local storage. When you return to
    [marimo.app](https://marimo.app), the last notebook you worked on will be
    re-opened. You can also click a button to save your notebook to
    the [Community Cloud](community_cloud/index.md).

### Share via links

At [marimo.app](https://marimo.app), save your notebook and then click the
`Create permalink` button to generate a shareable permalink to your
notebook.

Please be aware that marimo permalinks are publicly accessible.

### Creating playground notebooks from GitHub

Use the "New > Open from URL" menu item to paste a link to a GitHub notebook.

### Creating playground notebooks from local notebooks

In the marimo editor's notebook action menu, use `Share > Create WebAssembly
link` to get a `marimo.app/...` URL representing your notebook:

<div align="center">
<figure>
<img src="/_static/share-wasm-link.gif"/>
</figure>
</div>

WASM notebooks come with common Python packages installed, but you may need to
[install additional packages using micropip](../wasm.md#supported-packages).

The obtained URL encodes your notebook code as a parameter, so it can be
quite long. If you want a URL that's easier to share, you can [create a
shareable permalink](#share-via-links).

## Configuration

Your `marimo.app` URLs can be configured using the following parameters.

### Read-only mode

To view a notebook in read-only mode, with
code cells locked, append `&mode=read` to your URL's list of query parameters
(or `?mode=read` if your URL doesn't have a query string).

Example:

- `https://marimo.app/l/83qamt?mode=read`

### Hide header for embedding

To hide the `marimo.app` header, append `&embed=true` to your URL's list of query
parameters (or `?embed=true` if your URL doesn't have a query string).

Example:

- `https://marimo.app/l/83qamt?embed=true`
- `https://marimo.app/l/83qamt?mode=read&embed=true`

See the [section on embedding](#embedding-in-other-web-pages) for examples of
how to embed marimo notebooks in your own webpages.

### Excluding code

By default, WASM notebooks expose your Python code to viewers. If you've
enabled read-only mode, you can exclude code with
`&include-code=false`. If you want to include code but have it be hidden
by default, use the parameter `&show-code=false`.

A sufficiently determined user would still be able
to obtain your code, so **don't** think of this as a security feature; instead,
think of it as an aesthetic or practical choice.

## Embedding in other web pages

WASM notebooks can be embedded into other webpages using the HTML `<iframe>`
tag.

### Embedding a blank notebook

Use the following snippet to embed a blank marimo notebook into your web page,
providing your users with an interactive code playground.

```html
<iframe
  src="https://marimo.app/l/aojjhb?embed=true"
  width="100%"
  height="300"
  frameborder="0"
></iframe>
```

<iframe src="https://marimo.app/l/aojjhb?embed=true" width="100%" height="300" class="demo" frameBorder="0"></iframe>

### Embedding an existing notebook

To embed existing marimo notebooks into a webpage, first, [obtain a
URL to your notebook](#creating-and-sharing-wasm-notebooks), then put it in an iframe.

```html
<iframe
  src="https://marimo.app/l/c7h6pz?embed=true"
  width="100%"
  height="300"
  frameborder="0"
></iframe>
```

<iframe src="https://marimo.app/l/c7h6pz?embed=true" width="100%" height="600" class="demo" frameBorder="0"></iframe>

After obtaining a URL to your
notebook,

### Embedding an existing notebook in read-only mode

You can optionally render embedded notebooks in read-only mode by appending
`&mode=read` to your URL.

```html
<iframe
  src="https://marimo.app/l/c7h6pz?mode=read&embed=true"
  width="100%"
  height="300"
  frameborder="0"
></iframe>
```

<iframe src="https://marimo.app/l/c7h6pz?mode=read&embed=true" width="100%" height="600" class="demo" frameBorder="0"></iframe>
