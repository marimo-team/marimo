# Run as an app

The marimo CLI lets you run any notebook as an app: `marimo run` hides the
notebook's code and starts a web server that hosts the resulting app. 

```
Usage: marimo run [OPTIONS] NAME

  Run as an app in read-only mode.

  If NAME is a url, the app will be downloaded to a temporary file.

  Example:

      * marimo run your_app.py

Options:
  -p, --port INTEGER  Port to attach to.
  --headless          Don't launch a browser.
  --help              Show this message and exit.
```
