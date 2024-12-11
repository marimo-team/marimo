from pathlib import Path

import click

from marimo._cli.print import echo, green
from marimo._server.utils import find_free_port


@click.command(
    help="""Serve an WebAssembly HTML notebook.

This will start a simple HTTP server to serve the HTML file with
the proper headers required for marimo's WebAssembly.

This is useful for testing the notebook in the browser,
but is not recommended for production.
Instead, you should use a proper web server to serve the notebook.

Example:

  \b
  * marimo serve notebook.html

"""
)
@click.argument("filename", required=True, type=click.Path(exists=True))
def serve(filename: str) -> None:
    filepath = Path(filename)

    # If it is not an index.html, add it
    if not filepath.name.endswith(".html"):
        filepath = filepath / "index.html"
        if not filepath.exists():
            raise click.UsageError(
                f"File {filepath} does not exist. Please provide a valid HTML file."
            )

    import http.server
    import socketserver

    directory = Path(filename).parent
    handler = http.server.SimpleHTTPRequestHandler
    handler.directory = str(directory)
    port = find_free_port(port=8000)
    url = f"http://localhost:{port}/{filename}"

    with socketserver.TCPServer(("", port), handler) as httpd:
        echo(f"Serving notebook at {green(url)}")
        httpd.serve_forever()
