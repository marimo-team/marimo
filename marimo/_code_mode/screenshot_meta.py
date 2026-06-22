# Copyright 2026 Marimo. All rights reserved.
"""Meta keys for wiring screenshot credentials through `HTTPRequest.meta`.

Code-mode tools running in the kernel need to call back into the marimo
server (e.g. `ctx.screenshot()` driving Playwright against the
kiosk page). The server stamps a trusted `server_url` and
`auth_token` onto each control request's `meta` dict; the runtime
side reads them when building the screenshot session.
"""

from __future__ import annotations

SCREENSHOT_SERVER_URL_KEY = "screenshot_server_url"
SCREENSHOT_AUTH_TOKEN_KEY = "screenshot_auth_token"
