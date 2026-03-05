# Publish to the web

You can publish [exported](../exporting/index.md) marimo notebooks to the web.

## molab (recommended)

The easiest way to publish and share interactive notebooks is with
[molab](https://molab.marimo.io/notebooks), our free cloud-hosted notebook environment.
With molab, you can:

- Share notebooks by links
- [Preview notebooks from GitHub](../molab.md#preview-notebooks-from-github) with full interactivity
- Share [open-in-molab badges](../molab.md#share-open-in-molab-badges) in READMEs and docs
- [Embed interactive notebooks](../molab.md#embed-in-other-webpages) in your own webpages
- Contribute to our [public gallery](public_gallery.md)

## Self-hosted options

If you need to self-host exported notebooks, the following guides cover publishing with
[WebAssembly](../wasm.md) — no backend infrastructure required.

| Guide                                                 | Description                                                  |
| ----------------------------------------------------- | ------------------------------------------------------------ |
| [GitHub](github.md)                                   | Share from GitHub, view outputs, publish to GitHub Pages      |
| [Embed in other webpages](embedding.md)              | Embed notebooks in other sites via iframes or islands         |
| [Cloudflare](cloudflare.md)                           | Publish interactive notebooks on Cloudflare                  |
| [Self-host WebAssembly notebooks](self_host_wasm.md)  | Self-hosting interactive WebAssembly (HTML export) notebooks |
| [OpenGraph previews](opengraph.md)                    | Configure titles, descriptions, and thumbnails for link previews |
| [Thumbnails](thumbnails.md)                           | Generate thumbnail images for OpenGraph previews and galleries |
