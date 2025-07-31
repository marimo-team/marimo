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
```

For a more complete example, see the [FastAPI example](https://github.com/marimo-team/marimo/tree/main/examples/frameworks/fastapi).

## Dynamic directory

If you'd like to create a server to dynamically load marimo notebooks from a directory, you can use the `with_dynamic_directory` method. This is useful if the contents of the directory change often, such as a directory of notebooks for a dashboard, without restarting the server.

```python
server = (
    marimo.create_asgi_app()
    .with_dynamic_directory(path="/dashboard", directory="./notebooks")
)
```

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
```

## Accessing Request Data

Inside your marimo notebooks, you can access the current request data using `mo.app_meta().request`. This is particularly useful when implementing authentication or accessing user data.

```python
import marimo as mo

# Access request data in your notebook
request = mo.app_meta().request
if request and request.user and request.user["is_authenticated"]:
    content = f"Welcome {request.user['username']}!"
else:
    content = "Please log in"

mo.md(content)
```

### Authentication Middleware Example

Here's an example of how to implement authentication middleware that populates `request.user`:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Add user data to the request scope
        # This will be accessible via mo.app_meta().request.user
        request.scope["user"] = {
            "is_authenticated": True,
            "username": "example_user",
            # Add any other user data
        }

        # Optional add metadata to the request
        request.scope["meta"] = {
            "some_key": "some_value",
        }

        response = await call_next(request)
        return response

# Add the middleware to your FastAPI app
app.add_middleware(AuthMiddleware)
```

The `request` object provides access to:

- `request.headers`: Request headers
- `request.cookies`: Request cookies
- `request.query_params`: Query parameters
- `request.path_params`: Path parameters
- `request.user`: User data added by authentication middleware
- `request.url`: URL information including path, query parameters
- `request.meta`: Metadata added by your custom middleware


### Documenting and Validating Query Parameters

When mounted apps accept [query parameters](../../api/query_params.md), it can be helpful to declare, validate, and document them with the help of a [Pydantic model](https://fastapi.tiangolo.com/tutorial/query-param-models/).

If a marimo app called `notebooks/items.py` is mounted to `/items`, declaring an endpoint with the same route will take the query parameters through Pydantic model validation first, then redirect to the marimo endpoint.


```python
# src/main.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import RedirectResponse
from marimo import create_asgi_app
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Annotated, Literal
from urllib.parse import urlencode


app = FastAPI()


class FilterParams(BaseModel):
    limit: int = Field(100, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"
    tags: list[str] = []


@app.get("/items")
async def marimo_items(
    request: Request, filter_query: Annotated[FilterParams, Query()]
):
    query_params = urlencode(filter_query.model_dump(), doseq=True)
    return RedirectResponse(url=f"/items/?{query_params}")


server = create_asgi_app(include_code=True, quiet=False)
notebooks_dir = Path(__file__).parent.parent / "notebooks"

for filename in notebooks_dir.iterdir():
    if filename.suffix == ".py":
        app_name = filename.stem
        server = server.with_app(path=f"/{app_name}", root=filename)


app.mount("/", server.build())
```