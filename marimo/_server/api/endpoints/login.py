# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qsl

from starlette.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
)

from marimo._server.api.auth import validate_auth
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
<title>marimo</title>
</head>
<body style="
    background-color: #f4f4f9;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    margin: 0;">
  <form method="POST" action="/auth/login" style="
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
    error = ""
    redirect_url = request.query_params.get("next", "/")

    if request.user.is_authenticated:
        return RedirectResponse("/", 302)

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

    return HTMLResponse(content=LOGIN_PAGE.format(error=error))


@router.get("/login", name="login_page")
async def login_page(request: Request) -> HTMLResponse:
    del request
    return HTMLResponse(content=LOGIN_PAGE.format(error=""))
