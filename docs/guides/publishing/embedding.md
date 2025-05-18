# Embedding

There are various ways to embed marimo notebooks in other web pages, such 
as web documentation, educational platforms, or static sites in general. Here
are two ways:

* Host on [GitHub Pages](github_pages.md) or [self-host WASM HTML](self_host_wasm.md),
  and `<iframe>` the published notebook.
* `<iframe>` a [playground](playground.md) notebook, and [customize the embedding](playground.md#embedding-in-other-web-pages) with query params.
  (This is what we do throughout docs.marimo.io.)
* Use the [marimo snippets](from_code_snippets.md) plugin to replace code snippets in HTML or markdown with interactive notebooks.

We plan to provide more turn-key solutions for static site generation with
marimo notebooks in the future.
