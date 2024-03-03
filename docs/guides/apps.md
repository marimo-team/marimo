# Run as an app

The marimo CLI lets you run any notebook as an app: `marimo run` lays out
the notebook as an app and starts a web server that hosts the resulting app.

By default, apps are laid out as a concetentation of their outputs, with
code hidden. You can customize the layout using marimo's built-in drag-and-drop
grid editor; you can also choose to include code in the app view.


## CLI 

```
Usage: marimo run [OPTIONS] NAME

  Run a notebook as an app in read-only mode.

  If NAME is a url, the notebook will be downloaded to a temporary file.

  Example:

      * marimo run notebook.py

Options:
  -p, --port INTEGER  Port to attach to.
  --host TEXT         Host to attach to.
  --headless          Don't launch a browser.
  --include-code      Include notebook code in the app.
  --base-url TEXT     Base URL for the server. Should start with a /.
  --help              Show this message and exit.
```

## Layout

While editing a notebook with `marimo edit`, you can preview the notebook
as an app by clicking the preview button in the bottom-left of the editor.
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
<blockquote class="twitter-tweet" data-media-max-width="560"><p lang="en" dir="ltr">New feature! Drag-and-drop notebook outputs to build an app using our grid editor.<br><br>Shipping in our next release — stay tuned! <a href="https://t.co/DQpstGAmKh">pic.twitter.com/DQpstGAmKh</a></p>&mdash; marimo (@marimo_io) <a href="https://twitter.com/marimo_io/status/1762595771504116221?ref_src=twsrc%5Etfw">February 27, 2024</a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
</figure>
<figcaption>Grid layout lets you drag and drop outputs to construct your app</figcaption>
</div>

marimo saves metadata about your constructed layout in a `layouts` folder;
make sure to include this folder when sharing your notebook so that others
can reconstruct your layout.


