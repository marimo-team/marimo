---
description: "Deploy marimo notebooks as interactive web apps. Customize layouts with drag-and-drop, add authentication, and share with users."
---

# Run as an app

The marimo CLI lets you run any notebook as an app: `marimo run` lays out
the notebook as an app and starts a web server that hosts the resulting app.

By default, apps are laid out as a concatenation of their outputs, with
code hidden. You can customize the layout using marimo's built-in drag-and-drop
grid editor; you can also choose to include code in the app view.

## CLI

Run marimo notebooks as apps with

```
marimo run notebook.py
```

View the [CLI documentation](../cli.md#marimo-run) for more details.

### Gallery

You can run multiple notebooks (or a directory of notebooks) as a gallery:

```bash
marimo run folder/
marimo run notebook_a.py notebook_b.py folder/
```

This shows a page with one card per notebook. Cards can use notebook OpenGraph metadata for the title, description, and thumbnail image. Configure [OpenGraph previews](publishing/opengraph.md) and optionally generate images with [Thumbnails](publishing/thumbnails.md).

If you run a single folder with watch mode (`marimo run folder/ --watch`), the gallery index is refreshed on subsequent workspace requests so file additions and deletions show up after refreshing the gallery page. See [Using your own editor](editor_features/watching.md) for watch behavior and security considerations.

## Layout

While editing a notebook with `marimo edit`, you can preview the notebook
as an app by clicking the preview button in the bottom-right of the editor.
(You can also use the command palette.)

!!! note "`layouts` folder"
   marimo saves metadata about your constructed layout in a `layouts` folder;
   make sure to include this folder when sharing or deploying your notebook
   so that others can reconstruct your layout. Include this folder in version
   control.

### Vertical layout

The default layout is the vertical layout: cell outputs are concatenated
vertically and code is hidden. When combined with marimo's [built-in functions
for laying out outputs](../api/layouts/index.md), as well as its configurable
app widths (configure via the notebook settings menu), the vertical layout can
successfully support a wide breadth of application user interfaces.

### Grid layout

If you prefer a drag-and-drop experience over
[programmatic layout](../api/layouts/index.md), consider using marimo's grid
editor for making your apps: with this editor, you simply drag outputs onto a
grid to arrange them on the page.

Enable the grid editor in the app preview, via a dropdown:

<div align="center">
  <figure>
    <blockquote class="twitter-tweet" data-media-max-width="560">
      <p lang="en" dir="ltr">
        <a href="https://t.co/DQpstGAmKh">pic.twitter.com/DQpstGAmKh</a>
      </p>&mdash; marimo (@marimo_io)
      <a href="https://twitter.com/marimo_io/status/1762595771504116221?ref_src=twsrc%5Etfw">February 27, 2024</a>
    </blockquote>
    <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
  </figure>
  <figcaption>Grid layout lets you drag and drop outputs to construct your app</figcaption>
</div>

### Slides layout

If you prefer a slideshow-like experience, you can use the slides layout. Enable the slides layout in the app preview, via the same dropdown as above.

<video muted controls loop playsinline width="100%" src="/_static/docs-slides-view.mp4" aria-label="Video showing the slides layout editor">
</video>

#### Features

- A slide minimap on the left where you can drag and drop slides to rearrange them.
- A config sidebar on the right where you can configure the type of each slide.
- Edit code and run cells by clicking the Code toggle or pressing `C`.
- Add speaker notes at the bottom of each slide and launch speaker view by pressing `S`.
- Powered by [reveal.js](https://revealjs.com/), so you can use most of its features like keyboard shortcuts, navigation, etc.

#### Export slides

Export a configured deck as static HTML or as an interactive WebAssembly app:

```bash
marimo export html presentation.py -o presentation.html
marimo export html-wasm presentation.py -o presentation --mode run
```

The WebAssembly export loads its assets over HTTP. Serve the output directory
locally with `python -m http.server --directory presentation`.

Both exports open in the slides layout and preserve slide types, fragments,
speaker notes, and deck settings. Static HTML captures the outputs from the
export run and supports reveal.js speaker view. WebAssembly HTML runs Python in
the browser, so controls remain reactive. Use static HTML when the presentation
needs speaker view.

Speaker notes are embedded in the HTML file and readable by anyone who
receives it.

#### Styling slides

The slides layout is rendered with [reveal.js](https://revealjs.com/), so you
can brand a deck with a custom CSS file (see [Theming](configuration/theming.md))
targeted at reveal.js's own classes.

Target `.reveal-viewport` for deck-wide styles, like a background or a logo
that appears on every slide:

```css
.reveal-viewport {
  background-color: #faf8f4;
}

/* Logo pinned to the top-right of every slide */
.reveal-viewport::after {
  content: "";
  position: absolute;
  top: 1.25rem;
  right: 1.5rem;
  width: 7.5rem;
  height: 2.5rem;
  background-image: url("./logo.png");
  background-repeat: no-repeat;
  background-position: right center;
  background-size: contain;
  z-index: 40;
}
```

To target a specific slide, use either its position or a [named cell](configuration/theming.md#targeting-cells):

```css
/* By position (stable as long as the cell order doesn't change) */
.reveal .slides > section:first-of-type { /* ... */ }
.reveal .slides > section:nth-of-type(3) { /* ... */ }

/* By named cell (best when you only care about one specific cell) */
[data-cell-name="title"] { /* ... */ }
```

For a full-bleed background on a single slide, style `.reveal-viewport` with
`:has()` rather than the `<section>` directly — reveal.js letterboxes slide
content, so painting only the `<section>` can leave margins around it:

```css
.reveal-viewport:has(.slides > section.present [data-cell-name="title"]) {
  background: linear-gradient(145deg, #1c1917 0%, #292524 45%, #1f2937 100%);
}
```

#### Notes

- The order of the slides is determined by the order of the cells in the notebook.
- For PDF export, use `marimo export pdf notebook.py --as=slides --raster-server=live` for slide-style output with better capture compatibility.

If you need more control over the layout, please file an issue on [GitHub](https://github.com/marimo-team/marimo/issues),
so we can properly prioritize this feature.
