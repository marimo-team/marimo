# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlparse

from starlette.authentication import requires
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

from marimo._server.api.auth import validate_auth
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

router = APIRouter()

# Minimal login page
LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>marimo</title>
</head>
<body style="
    background-color: #f4f4f9;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    margin: 0;">
  <form method="POST" action="{base_url}auth/login" style="
    padding: 20px;
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    width: 300px;
    text-align: center;">
    <div style="margin-bottom: 20px;">
      <label for="password" style="
        display: block;
        margin-bottom: 5px;
        font-size: 16px;
        font-family: Arial, sans-serif;
        color: #333;">Access Token / Password</label>
      <input id="password" name="password" type="password" style="
        width: 100%;
        box-sizing: border-box;
        padding: 8px;
        border: 1px solid #ccc;
        border-radius: 4px;">
    </div>
    <button type="submit" style="
        background-color: #1C7362;
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        width: 100%;
        font-size: 16px;">Login</button>
    <p style="color: red;">{error}</p>
  </form>
</body>
</html>
"""


@router.post("/login")
async def login_submit(request: Request) -> Response:
    """
    tags: [auth]
    summary: Submit login form
    requestBody:
        content:
            application/x-www-form-urlencoded:
                schema:
                    type: object
                    properties:
                        password:
                            type: string
                            description: Access token or password
    responses:
        302:
            description: Redirect to the next URL
            headers:
                Location:
                    schema:
                        type: string
        200:
            description: Login page
            content:
                text/html:
                    schema:
                        type: string
    """
    base_url = AppState(request).base_url or "/"
    base_url = _with_trailing_slash(base_url)

    error = ""
    redirect_url = request.query_params.get("next", base_url)

    # Validate redirect URL to prevent open redirect vulnerabilities
    # Reject protocol-relative URLs (e.g. //evil.com) which browsers
    # interpret as absolute URLs, bypassing scheme-based checks.
    parsed = urlparse(redirect_url)
    if parsed.netloc and parsed.netloc != request.url.netloc:
        redirect_url = base_url

    if request.method == "POST":
        body = (await request.body()).decode()
        data = dict(parse_qsl(body))
        password = data.get("password", "")
        if not password:
            error = "Password is required"
        else:
            success = validate_auth(request, data)
            if success:
                return RedirectResponse(redirect_url, 302)
            else:
                error = "Invalid password"
    elif request.user.is_authenticated:
        return RedirectResponse(redirect_url, 302)

    base_url = _with_trailing_slash(AppState(request).base_url or "/")
    html = LOGIN_PAGE.format(error=error, base_url=base_url)
    return HTMLResponse(
        content=html,
        headers={
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/login", name="login_page")
async def login_page(request: Request) -> HTMLResponse:
    base_url = AppState(request).base_url
    base_url = _with_trailing_slash(base_url)
    return HTMLResponse(
        content=LOGIN_PAGE.format(error="", base_url=base_url),
        headers={
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/token")
@requires("edit")
async def auth_token(request: Request) -> JSONResponse:
    """
    tags: [auth]
    summary: Get the auth token for the current session
    responses:
        200:
            description: The auth token (null if auth is disabled)
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            token:
                                type: string
                                nullable: true
    """
    state = AppState(request)
    no_cache = {"Cache-Control": "no-store"}
    if not state.enable_auth:
        return JSONResponse({"token": None}, headers=no_cache)
    return JSONResponse(
        {"token": str(state.session_manager.auth_token)}, headers=no_cache
    )


def _with_trailing_slash(url: str) -> str:
    if not url.endswith("/"):
        return url + "/"
    return url
