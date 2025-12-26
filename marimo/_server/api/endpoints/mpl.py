# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

import websockets

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.websockets import WebSocket


from marimo import _loggers
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

router = APIRouter()

figure_endpoints: dict[int, str] = {}


def mpl_fallback_handler(
    path_prefix: str = "",
) -> Callable[
    [Callable[[Request], Awaitable[Response]]],
    Callable[[Request], Awaitable[Response]],
]:
    """
    Args:
        path_prefix: Prefix to add to path when calling _mpl_handler (default "")
    """
    from starlette.responses import Response

    def decorator(
        func: Callable[[Request], Awaitable[Response]],
    ) -> Callable[[Request], Awaitable[Response]]:
        @wraps(func)
        async def wrapper(request: Request) -> Response:
            figure_num = request.path_params["figure"]
            path = request.path_params.get("path", "")
            response: Optional[Response] = None

            if figure_num in figure_endpoints:
                full_path = path_prefix + path if path_prefix else path
                response = await _mpl_handler(request, full_path, figure_num)

            # Fallback if no response or non-200 status
            if response is None or response.status_code != 200:
                try:
                    response = await func(request)
                except Exception as e:
                    LOGGER.error(f"Error in fallback handler: {e}")
                    response = Response(
                        content="Internal server error",
                        status_code=500,
                        media_type="text/plain",
                    )

            return response

        return wrapper

    return decorator


@router.get("/mpl/{figure:int}/_static/{path:path}")
@mpl_fallback_handler("_static/")
async def mpl_static(request: Request) -> Response:
    """Fallback for static files from matplotlib."""
    path = request.path_params["path"]
    from matplotlib.backends.backend_webagg_core import (
        FigureManagerWebAgg,
    )
    from starlette.staticfiles import StaticFiles

    static_app = StaticFiles(
        directory=FigureManagerWebAgg.get_static_file_path()  # type: ignore[no-untyped-call]
    )
    return await static_app.get_response(path, request.scope)


@router.get("/mpl/{figure:int}/_images/{path:path}")
@mpl_fallback_handler(path_prefix="_images/")
async def mpl_images(request: Request) -> Response:
    """Fallback for image files from matplotlib."""
    path = request.path_params["path"]
    import matplotlib as mpl
    from starlette.staticfiles import StaticFiles

    static_app = StaticFiles(directory=Path(mpl.get_data_path(), "images"))
    return await static_app.get_response(path, request.scope)


@router.get("/mpl/{figure:int}/mpl.js")
@mpl_fallback_handler()
async def mpl_js(request: Request) -> Response:
    """Fallback for mpl.js from marimo's internal handler."""
    from marimo._plugins.stateless.mpl._mpl import mpl_js

    return await mpl_js(request)


@router.get("/mpl/{figure:int}/custom.css")
@mpl_fallback_handler()
async def mpl_custom_css(request: Request) -> Response:
    """Fallback for custom.css from marimo's internal handler."""
    from marimo._plugins.stateless.mpl._mpl import mpl_custom_css

    return await mpl_custom_css(request)


async def _mpl_handler(
    request: Request, path: str, figurenum: int
) -> Response:
    """
    Unified proxy function for matplotlib server requests.

    Args:
        request: The incoming request
        path: The remaining path to proxy
        figurenum: The figure number

    Returns:
        Response from the matplotlib server or error response
    """
    from starlette.responses import Response

    # Proxy to matplotlib server
    # Determine the target port
    port = figure_endpoints.get(figurenum, None)

    if port is None:
        LOGGER.info(
            f"Security violation: Attempt to access unauthorized figure {figurenum}"
        )
        return Response(
            content="Unauthorized access",
            status_code=403,
            media_type="text/plain",
        )

    # Construct target URL
    target_url = f"http://localhost:{port}/{path}"
    LOGGER.debug(f"Proxying {request.method} -> {target_url}")

    # Prepare headers (exclude problematic headers)
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    try:
        import urllib.parse
        import urllib.request
        from urllib.error import URLError

        # Construct full URL with query parameters
        if request.query_params:
            query_string = urllib.parse.urlencode(request.query_params)
            full_url = f"{target_url}?{query_string}"
        else:
            full_url = target_url

        # Prepare request data
        data = None
        if request.method in ("POST", "PUT", "PATCH"):
            data = await request.body()

        # Create urllib request
        req = urllib.request.Request(
            full_url, data=data, headers=headers, method=request.method
        )

        # Execute request in thread pool to avoid blocking
        def _make_request() -> dict[str, Any]:
            try:
                with urllib.request.urlopen(req, timeout=30.0) as response:
                    return {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "content": response.read(),
                    }
            except URLError as e:
                raise ConnectionError() from e

        loop = asyncio.get_event_loop()
        response_data = await loop.run_in_executor(None, _make_request)

        return Response(
            content=response_data["content"],
            status_code=response_data["status"],
            headers=response_data["headers"],
            media_type=response_data["headers"].get("content-type"),
        )

    except ConnectionError:
        LOGGER.info(f"Failed to connect to matplotlib server at port {port}")
        return Response(
            content="Matplotlib server is not available. Please rerun this cell or restart the service.",
            status_code=503,
            media_type="text/plain",
        )
    except Exception as e:
        LOGGER.error(f"Error proxying to matplotlib server: {e}")
        return Response(
            content="Internal server error",
            status_code=500,
            media_type="text/plain",
        )


@router.get("/mpl/{figure:int}/{path:path}")
async def mpl_handler(request: Request) -> Response:
    path = request.path_params["path"]
    figurenum = request.path_params["figure"]
    return await _mpl_handler(request, path, figurenum)


@router.websocket("/mpl/{port}/ws")
async def mpl_websocket(websocket: WebSocket) -> None:
    """Proxy WebSocket connections to matplotlib server."""
    global figure_endpoints
    port = str(websocket.path_params["port"])

    await websocket.accept()

    # Construct target WebSocket URL with query parameters
    query_params = dict(websocket.query_params)
    query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
    target_ws_url = f"ws://localhost:{port}/ws"
    if query_string:
        target_ws_url += f"?{query_string}"

    # get figure from query params
    figure_num = None
    try:
        figure_num = query_params.get("figure")
        if figure_num is not None:
            figure_endpoints[int(figure_num)] = f"{port}"
    except (TypeError, ValueError):
        LOGGER.warning(
            f"Invalid figure number in WebSocket connection: {query_params.get('figure')}"
        )
        pass

    try:
        async with websockets.connect(target_ws_url) as mpl_ws:

            async def forward_to_mpl() -> None:
                try:
                    async for message in websocket.iter_text():
                        await mpl_ws.send(message)
                except Exception as e:
                    LOGGER.debug(f"Client->Server forwarding ended: {e}")

            async def forward_to_client() -> None:
                try:
                    async for message in mpl_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except Exception as e:
                    LOGGER.debug(f"Server->Client forwarding ended: {e}")

            await asyncio.gather(
                forward_to_mpl(), forward_to_client(), return_exceptions=True
            )

    except Exception as e:
        LOGGER.error(f"WebSocket proxy error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
