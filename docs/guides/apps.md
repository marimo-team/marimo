# Run as an app

The marimo CLI lets you run any notebook as an app: `marimo run` hides the
notebook's code and starts a web server that hosts the resulting app.

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
