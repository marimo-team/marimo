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

## Layout

While editing a notebook with `marimo edit`, you can preview the notebook
as an app by clicking the preview button in the bottom-right of the editor.
(You can also use the command palette.)

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

marimo saves metadata about your constructed layout in a `layouts` folder;
make sure to include this folder when sharing your notebook so that others
can reconstruct your layout.

### Slides layout

If you prefer a slideshow-like experience, you can use the slides layout. Enable the slides layout in the app preview, via the same dropdown as above.

!!! info "See slides layout in action"
    Check out this [example notebook](https://marimo.io/p/@gvarnavides/stem-probes) that runs in slides mode, powered by our [Community Cloud](./publishing/community_cloud/).

Unlike the grid layout, the slides are much less customizable:

- The order of the slides is determined by the order of the cells in the notebook.
- The slides do not support drag-and-drop rearrangement or resizing.
- All outputs are shown and all code is hidden.

If you need more control over the layout, please file an issue on [GitHub](https://github.com/marimo-team/marimo/issues),
so we can properly prioritize this feature.
