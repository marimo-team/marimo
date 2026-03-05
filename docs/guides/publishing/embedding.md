# Embed in other webpages

There are various ways to embed marimo notebooks in other webpages, such
as web documentation, educational platforms, or static sites in general.

## molab (recommended)

The easiest way to embed interactive notebooks is with [molab](../molab.md).
Either push your code to GitHub or construct a URL directly from the notebook source,
then embed in an iframe; this is what we do throughout this documentation website.

/// tab | Code

```html
<iframe
    src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
    sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
    allow="microphone"
    allowfullscreen
    loading="lazy"
>
</iframe>
```

///

/// tab | Live Example

<div class="demo-container">
    <iframe
        src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
        class="demo large"
        sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
        allow="microphone"
        allowfullscreen
        loading="lazy"
    >
    </iframe>
</div>

///

See the [molab embedding docs](../molab.md#embed-in-other-webpages) for details
on URL parameters and configuration.

## Self-hosted options

If you need to self-host, you can also embed notebooks by:

* Hosting on [GitHub Pages](github.md#publish-to-github-pages) or [self-hosting WASM HTML](self_host_wasm.md),
  and iframing the published notebook.
* Using [marimo islands](../exporting/webassembly_html.md#embed-marimo-outputs-in-html-using-islands) to embed individual cell outputs directly in your HTML pages.

## Iframe sandbox configuration

When embedding marimo notebooks in sandboxed iframes, proper configuration is essential for full functionality. marimo is designed to gracefully degrade when certain features are restricted, but understanding these requirements will help you provide the best experience.

### Required sandbox attributes

For marimo to function properly in an iframe, you need this **minimum** sandbox attribute:

```html
<iframe
  src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm"
  sandbox="allow-scripts"
  width="100%"
  height="600"
></iframe>
```

* **`allow-scripts`**: Required for JavaScript execution (essential for marimo to run)

!!! note "Basic Functionality"
    With only `allow-scripts`, marimo will work but with limitations: WebSocket connections will function, but storage will be in-memory only (state resets on page reload), and clipboard access will use browser prompts instead of the clipboard API.

### Recommended sandbox attributes

For the best user experience, include these additional attributes:

```html
<iframe
  src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm"
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
