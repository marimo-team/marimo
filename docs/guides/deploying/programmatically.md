# Running the marimo backend programmatically

marimo can be run programmatically using the `marimo` module. This is useful when you want to run marimo as part of a larger application or when you need to customize the behavior of marimo (e.g. middleware, custom error handling, authentication, routing, etc).

## FastAPI Example

Here's an example of how you can run a marimo application programmatically using FastAPI:

```python
from typing import Annotated, Callable, Coroutine
from fastapi.responses import HTMLResponse, RedirectResponse
import marimo
from fastapi import FastAPI, Form, Request, Response


# Create a marimo asgi app
server = (
    marimo.create_asgi_app()
    .with_app(path="", root="./pages/index.py")
    .with_app(path="/dashboard", root="./pages/dashboard.py")
    .with_app(path="/sales", root="./pages/sales.py")
)

# Create a FastAPI app
app = FastAPI()

app.add_middleware(auth_middleware)
app.add_route("/login", my_login_route, methods=["POST"])

app.mount("/", server.build())

# Run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)

For a more complete example, see the [FastAPI example](https://github.com/marimo-team/marimo/tree/main/examples/frameworks/fastapi).

## Dynamic directory

If you'd like to create a server to dynamically load marimo notebooks from a directory, you can use the `with_dynamic_directory` method. This is useful if the contents of the directory change often, such as a directory of notebooks for a dashboard, without restarting the server.

```python
server = (
    marimo.create_asgi_app()
    .with_dynamic_directory(path="/dashboard", directory="./notebooks")
)

If the notebooks in the directory are expected to be static, it is better to use the `with_app` method and loop through the directory contents.

```python
from pathlib import Path
server = marimo.create_asgi_app()
app_names: list[str] = []

notebooks_dir = Path(__file__).parent / "notebooks"

for filename in sorted(notebooks_dir.iterdir()):
    if filename.suffix == ".py":
        app_name = filename.stem
        server = server.with_app(path=f"/{app_name}", root=filename)
        app_names.append(app_name)
