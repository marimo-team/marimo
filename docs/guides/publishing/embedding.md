# Embedding

There are various ways to embed marimo notebooks in other web pages, such
as web documentation, educational platforms, or static sites in general. Here
are the main approaches:

* Host on [GitHub Pages](github_pages.md) or [self-host WASM HTML](self_host_wasm.md),
  and `<iframe>` the published notebook.
* `<iframe>` a [playground](playground.md) notebook, and [customize the embedding](playground.md#embedding-in-other-web-pages) with query params.
  (This is what we do throughout https://docs.marimo.io.)
* Use the [marimo snippets](from_code_snippets.md) plugin to replace code snippets in HTML or markdown with interactive notebooks.

## Iframe Sandbox Configuration

When embedding marimo notebooks in sandboxed iframes, proper configuration is essential for full functionality. marimo is designed to gracefully degrade when certain features are restricted, but understanding these requirements will help you provide the best experience.

### Required Sandbox Attributes

For marimo to function properly in an iframe, you need this **minimum** sandbox attribute:

```html
<iframe
  src="https://marimo.app/your-notebook"
  sandbox="allow-scripts"
  width="100%"
  height="600"
></iframe>
```

* **`allow-scripts`**: Required for JavaScript execution (essential for marimo to run)

!!! note "Basic Functionality"
    With only `allow-scripts`, marimo will work but with limitations: WebSocket connections will function, but storage will be in-memory only (state resets on page reload), and clipboard access will use browser prompts instead of the clipboard API.

### Recommended Sandbox Attributes

For the best user experience, include these additional attributes:

```html
<iframe
  src="https://marimo.app/your-notebook"
  sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
  allow="microphone"
  allowfullscreen
  width="100%"
  height="600"
></iframe>
```

**Additional Attributes:**

* **`allow-same-origin`**: Enables persistent storage (localStorage) and full clipboard API. Only use this if you trust the content of the iframe or the iframe URL is hosted on a different domain.
* **`allow-downloads`**: Enables downloading notebook outputs, data exports, and screenshots
* **`allow-popups`**: Allows opening links and notebooks in new tabs
* **`allowfullscreen`** (attribute, not sandbox): Enables fullscreen mode for slides and outputs

**Permission Policy:**

* **`allow="microphone"`**: Required for `mo.ui.microphone()` widget functionality

!!! tip "Security Considerations"
    Only use `allow-same-origin` with trusted content or the iframe URL is hosted on a different domain. Combining `allow-scripts` and `allow-same-origin` allows the iframe to remove the sandbox attribute entirely, making the iframe as powerful as if it weren't sandboxed at all.

### Example: Full Configuration

Here's a complete example with all recommended settings:

```html
<iframe
  src="https://marimo.app/l/your-notebook-id?embed=true&mode=read"
  sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-downloads-without-user-activation"
  allow="microphone"
  allowfullscreen
  width="100%"
  height="600"
  style="border: 1px solid #ddd; border-radius: 8px;"
></iframe>
```
