# Run as an app

The marimo CLI lets you run any notebook as an app: `marimo run` lays out
the notebook as an app and starts a web server that hosts the resulting app.

By default, apps are laid out as a concatenation of their outputs, with
code hidden. You can customize the layout using marimo's built-in drag-and-drop
grid editor; you can also choose to include code in the app view.

## CLI

```
Usage: marimo run [OPTIONS] NAME [ARGS]...

  Run a notebook as an app in read-only mode.

  If NAME is a url, the notebook will be downloaded to a temporary file.

  Example:

      * marimo run notebook.py

Options:
  -p, --port INTEGER             Port to attach to.
  --host TEXT                    Host to attach to.  [default: 127.0.0.1]
  --proxy TEXT                   Address of reverse proxy.
  --headless                     Don't launch a browser.
  --token / --no-token           Use a token for authentication. This enables
                                 session-based authentication. A random token
                                 will be generated if --token-password is not
                                 set.

                                 If --no-token is set, session-based
                                 authentication will not be used.  [default:
                                 no-token]
  --token-password TEXT          Use a specific token for authentication. This
                                 enables session-based authentication. A
                                 random token will be generated if not set.
  --include-code                 Include notebook code in the app.
  --watch                        Watch the file for changes and reload the
                                 app. If watchdog is installed, it will be
                                 used to watch the file. Otherwise, file
                                 watcher will poll the file every 1s.
  --base-url TEXT                Base URL for the server. Should start with a
                                 /.
  --allow-origins TEXT           Allowed origins for CORS. Can be repeated.
  --redirect-console-to-browser  Redirect console logs to the browser console.
  --sandbox                      Run the command in an isolated virtual
                                 environment using 'uv run --isolated'.
                                 Requires `uv`.
  --help                         Show this message and exit.
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

Unlike the grid layout, the slides are much less customizable:

- The order of the slides is determined by the order of the cells in the notebook.
- The slides do not support drag-and-drop rearrangement or resizing.
- All outputs are shown and all code is hidden.

If you need more control over the layout, please file an issue on [GitHub](https://github.com/marimo-team/marimo/issues),
so we can properly prioritize this feature.
