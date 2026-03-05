# Publish to the web

You can publish marimo notebooks to the web as interactive editable notebooks,
readonly web apps, or [static documents](../exporting/index.md).

## molab (recommended)

The easiest way to publish and share interactive notebooks is with
[molab](../molab.md), our free cloud-hosted notebook environment.
With molab, you can:

- Share notebooks with a link — no export or hosting setup required
- [Preview notebooks from GitHub](../molab.md#preview-notebooks-from-github) with full interactivity
- [Embed interactive notebooks](../molab.md#embed-in-other-webpages) in your own webpages
- Share [open-in-molab badges](../molab.md#share-open-in-molab-badges) in READMEs and docs

**[Get started with molab →](../molab.md)**

## Self-hosted options

If you need to self-host, the following guides cover publishing with
[WebAssembly](../wasm.md) — no backend infrastructure required.

| Guide                                                 | Description                                                  |
| ----------------------------------------------------- | ------------------------------------------------------------ |
| [GitHub](github.md)                                   | Share from GitHub, view outputs, publish to GitHub Pages      |
| [Embed in other webpages](embedding.md)              | Embed notebooks in other sites via iframes or islands         |
| [Cloudflare](cloudflare.md)                           | Publish interactive notebooks on Cloudflare                  |
| [Quarto](../exporting/quarto.md)                      | Publish reactive websites with Quarto from markdown          |
| [Self-host WebAssembly notebooks](self_host_wasm.md)  | Self-hosting interactive WebAssembly (HTML export) notebooks |
