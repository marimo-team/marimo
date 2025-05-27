# Authentication

marimo provides a simple way to add token/password protection to your marimo server. Given that authentication is a complex topic, marimo does not provide a built-in authentication/authorization system, but instead makes it easy to add your own through ASGI middleware.

## Enabling Basic Authentication

Authentication is enabled by default when running `marimo edit/tutorial/new`. To disable authentication, you may pass `--no-token` to your `marimo edit/run/new` command from the Terminal. The auth token will be randomly generated when in `Edit mode` and deterministically generated in `Run mode` (based on the code of the notebook). However, you can also pass your own token/password using the `--token-password` flag.

```bash
marimo run my_notebook.py --token --token-password="sup3rs3cr3t"
```

### Ways to Authenticate

In order to authenticate, you must either pass the token as a password in the `Authorization` header, or as a query parameter under `access_token` in the URL.

1. Enter the token in the login page:

If you try to access marimo from a browser, you will be redirected to a login page where you can enter the token.

2. Query parameter:

To authenticate using a query parameter, you must pass the token as a query parameter under `access_token` in the URL. For example, to authenticate with the token `sup3rs3cr3t`, you would pass the query parameter `http://localhost:2718?access_token=sup3rs3cr3t`.

For convenience, when running locally, marimo will automatically open the URL with the query parameter in your default browser.

3. Basic Authorization header:

To authenticate using the `Authorization` header, you must pass the token as a password in the `Authorization` header using the [Basic authentication scheme](https://developer.mozilla.org/en-US/docs/Web/HTTP/Authentication). For example, to authenticate with the token `sup3rs3cr3t`, you would pass the header `Authorization Basic base64("any_username:sup3rs3cr3t")`.

This is not necessary when using a browser, as the marimo server will redirect you to a minimal login page where you can enter the token.

## Custom Authentication

If you choose to make your marimo application public, you may want to add your own authentication system, along with authorization, rate limiting, etc. You can do this by creating a marimo application programmatically and adding your own middleware to the ASGI application.

Here's an example of how you can add authentication to a marimo application using FastAPI:

```python
from typing import Annotated, Callable, Coroutine
from fastapi.responses import HTMLResponse, RedirectResponse
import marimo
from fastapi import FastAPI, Form, Request, Response
# Custom auth middleware and login page
from my_auth_module import auth_middleware, my_login_route


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

For for a full example on implementing OAuth2 with FastAPI, see the [FastAPI OAuth2 example](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).
