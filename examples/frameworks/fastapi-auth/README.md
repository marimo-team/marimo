# FastAPI + marimo: Authentication Middleware

This example shows the recommended pattern for passing user info into marimo
notebooks via `mo.app_meta().request.user` and `mo.app_meta().request.meta`.

It includes:

- Login / logout with session cookies
- A **pure ASGI middleware** that sets `scope["user"]` and `scope["meta"]` for
  both HTTP and WebSocket connections
- A marimo notebook that reads user info via `mo.app_meta().request`

### Why pure ASGI middleware?

marimo uses WebSocket for real-time communication. Starlette's
`BaseHTTPMiddleware` only runs for HTTP requests, so `scope["user"]` set there
is not visible on WebSocket connections. A pure ASGI middleware handles both.

## Running the app

1. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
2. Run the app with `uv run --no-project main.py`
3. Open http://localhost:8000/ and log in with `admin` / `password123`
4. The notebook cell will display the authenticated user and meta data
