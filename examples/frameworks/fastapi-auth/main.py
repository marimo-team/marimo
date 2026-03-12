# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastapi",
#     "marimo",
#     "starlette",
#     "uvicorn",
#     "itsdangerous",
#     "python-multipart",
# ]
# ///
"""Example: Authentication middleware that passes user info into marimo notebooks.

This shows the recommended pattern for authentication with marimo when using
FastAPI. It uses a pure ASGI middleware (not BaseHTTPMiddleware) so that
scope["user"] and scope["meta"] are set for both HTTP *and* WebSocket
connections.

The user info is then available in notebooks via:

    request = mo.app_meta().request
    username = request.user["username"]

Run with:
    uv run --no-project main.py

Then open http://localhost:8000/ and log in with admin / password123.
"""

import os
import logging

import marimo
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

notebook_dir = os.path.dirname(__file__)
notebook_path = os.path.join(notebook_dir, "notebook.py")

# Simulated user database (replace with a real database in production)
users_db = {"admin": "password123"}

app = FastAPI()


# Pure ASGI middleware — runs for both HTTP and WebSocket requests.
# This is the recommended pattern for passing user/meta into marimo.
#
# Important: Do NOT use Starlette's BaseHTTPMiddleware here.
# BaseHTTPMiddleware only processes HTTP requests, not WebSocket
# connections. marimo uses WebSocket for real-time communication,
# so scope["user"] and scope["meta"] would be lost.
#
# This is a simplified version of authentication and you may want to use
# starlette.middleware.authentication.AuthenticationMiddleware instead.
class AuthMiddleware:
    # Paths that don't require authentication
    PUBLIC_PATHS = {"/login"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # SessionMiddleware has already run, so scope["session"] is available.
        session = scope.get("session", {})
        username = session.get("username")

        if username:
            # Set user/meta so marimo can read them via mo.app_meta().request
            scope["user"] = {
                "is_authenticated": True,
                "username": username,
            }
            scope["meta"] = {"role": "admin"}
            await self.app(scope, receive, send)
            return

        # Not logged in — block unauthenticated access.
        path = scope.get("path", "")

        # Allow public paths through without authentication.
        if path in self.PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        # Reject unauthenticated WebSocket connections.
        if scope["type"] == "websocket":
            from starlette.websockets import WebSocket

            ws = WebSocket(scope, receive, send)
            await ws.close(code=4003)
            return

        # Redirect unauthenticated HTTP requests to /login.
        response = Response(
            status_code=302, headers={"location": "/login"}
        )
        await response(scope, receive, send)


# Middleware ordering: In Starlette, the LAST added middleware is the
# OUTERMOST (runs first). We need SessionMiddleware to run before
# AuthMiddleware so that scope["session"] is populated. So we add
# AuthMiddleware first (innermost) and SessionMiddleware last (outermost).
app.add_middleware(AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "change-me-in-production"),
)

LOGIN_PAGE = """\
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif">
  <form method="post" action="/login" style="width:300px">
    <h2>Login</h2>
    {error}
    <div style="margin-bottom:8px">
      <label>Username</label><br>
      <input name="username" required style="width:100%;padding:6px">
    </div>
    <div style="margin-bottom:8px">
      <label>Password</label><br>
      <input name="password" type="password" required style="width:100%;padding:6px">
    </div>
    <button type="submit" style="width:100%;padding:8px">Log in</button>
  </form>
</body>
</html>
"""


@app.get("/login")
async def get_login():
    return HTMLResponse(LOGIN_PAGE.format(error=""))


@app.post("/login")
async def post_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username in users_db and password == users_db[username]:
        request.session["username"] = username
        logger.info("User %s logged in", username)
        return RedirectResponse(url="/", status_code=302)
    logger.warning("Failed login attempt for %s", username)
    return HTMLResponse(
        LOGIN_PAGE.format(
            error='<p style="color:red">Invalid credentials</p>'
        )
    )


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")


# Mount marimo
marimo_app = (
    marimo.create_asgi_app(include_code=True)
    .with_app(path="/", root=notebook_path)
    .build()
)
app.mount("/", marimo_app)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
