# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict
from urllib.parse import urlencode

from starlette.authentication import has_required_scope, requires
from starlette.exceptions import HTTPException
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from starlette.staticfiles import StaticFiles

from marimo import _loggers
from marimo._cli.sandbox import SandboxMode
from marimo._config.manager import get_default_config_manager
from marimo._config.reader import find_nearest_pyproject_toml
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._output.utils import uri_decode_component, uri_encode_component
from marimo._runtime.virtual_file import (
    EMPTY_VIRTUAL_FILE,
    read_virtual_file_chunked,
)
from marimo._server.api.auth import TOKEN_QUERY_PARAM
from marimo._server.api.deps import AppState
from marimo._server.files.path_validator import PathValidator
from marimo._server.router import APIRouter
from marimo._server.templates.templates import (
    home_page_template,
    inject_script,
    notebook_page_template,
)
from marimo._session.model import SessionMode
from marimo._utils.async_path import AsyncPath
from marimo._utils.paths import (
    MARIMO_DIR_NAME,
    marimo_package_path,
    normalize_path,
    notebook_output_dir,
)

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for serving static assets
router = APIRouter()

# Root directory for static assets
root = normalize_path(marimo_package_path() / "_static")

server_config = (
    get_default_config_manager(current_path=None)
    .get_config()
    .get("server", {})
)

assets_dir = root / "assets"
follow_symlinks = server_config.get("follow_symlink", False)


def _missing_index_html_detail() -> str:
    repo_root = marimo_package_path().parent
    if (repo_root / "frontend").exists() and (
        repo_root / "pyproject.toml"
    ).exists():
        return (
            "index.html not found. Did you run `make fe`? "
            "Restart marimo after building."
        )
    return "index.html not found and no asset_url configured"


def _has_symlinks(directory: Path) -> bool:
    """Check if a directory is a symlink or contains symlinked files."""
    if directory.is_symlink():
        return True
    try:
        # Check a small sample of files for symlinks
        for i, child in enumerate(directory.iterdir()):
            if child.is_symlink():
                return True
            if i >= 1:
                break
    except OSError:
        pass
    return False


if not follow_symlinks and _has_symlinks(assets_dir):
    LOGGER.error(
        "Assets directory contains symlinks but follow_symlink=false.\n"
        "This commonly happens with package managers like pdm/uv "
        "that use symlinks for installed packages.\n"
        "To fix this:\n"
        "1. Run 'marimo config show' to see your current config\n"
        "2. Add 'follow_symlink = true' under the [server] section in your config\n"
        "3. Restart marimo\n\n"
        "Example config:\n"
        "[server]\n"
        "follow_symlink = true"
    )

try:
    router.mount(
        "/assets",
        app=StaticFiles(
            directory=assets_dir,
            follow_symlink=follow_symlinks,
        ),
        name="assets",
    )
except RuntimeError:
    LOGGER.error("Static files not found, skipping mount")

FILE_QUERY_PARAM_KEY = "file"

# Hardening headers for HTML page responses in edit/home mode. These
# supplement the token-stripping redirect below by preventing any outbound
# fetch from the HTML page from leaking a transiently-present access_token
# via `Referer`, and by disabling MIME sniffing on the HTML response.
_HTML_SECURITY_HEADERS: dict[str, str] = {
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def _strip_access_token_redirect(request: Request) -> RedirectResponse:
    """Build a redirect to the current URL with access_token removed.

    By the time this runs, `validate_auth` has already matched the query
    param against the server's auth token and promoted it to a session
    cookie. Redirecting before any JavaScript runs prevents a
    pre-execution XSS, a third-party subresource, or browser history from
    capturing the plaintext token.
    """
    stripped = request.url.remove_query_params(TOKEN_QUERY_PARAM)
    target = stripped.path
    if stripped.query:
        target = f"{target}?{stripped.query}"
    return RedirectResponse(
        url=target,
        status_code=303,
        headers=_HTML_SECURITY_HEADERS,
    )


def _login_redirect(request: Request) -> RedirectResponse:
    """Build a relative redirect to the login page for unauthenticated users.

    Starlette's built-in `@requires(redirect=...)` builds the Location from
    `request.url_for(...)` and embeds `str(request.url)` as `next=`. Both
    of those use the request's `Host` header, so behind a reverse proxy
    that doesn't rewrite `Host` the browser is sent to an internal
    address. Emitting a relative `Location` sidesteps that — browsers
    resolve it against the URL they themselves used, regardless of what
    the proxy forwarded.

    See https://github.com/marimo-team/marimo/issues/9249.
    """
    next_url = request.url.path
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    login_path = request.app.url_path_for("auth:login_page")
    return RedirectResponse(
        url=f"{login_path}?{urlencode({'next': next_url})}",
        status_code=303,
    )


@router.get("/og/thumbnail", include_in_schema=False)
@requires("read")
def og_thumbnail(*, request: Request) -> Response:
    """Serve a notebook thumbnail for gallery/OpenGraph use."""
    from pathlib import Path

    from marimo._metadata.opengraph import (
        DEFAULT_OPENGRAPH_PLACEHOLDER_IMAGE_GENERATOR,
        OpenGraphContext,
        is_https_url,
        resolve_opengraph_metadata,
    )
    from marimo._utils.http import HTTPException, HTTPStatus
    from marimo._utils.paths import normalize_path

    app_state = AppState(request)
    file_key = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.workspace.get_unique_file_key()
    )
    if not file_key:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="File not found"
        )

    notebook_path = app_state.session_manager.workspace.resolve(file_key)
    if notebook_path is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="File not found"
        )

    notebook_dir = normalize_path(Path(notebook_path)).parent
    marimo_dir = notebook_output_dir(notebook_path)

    # User-defined OpenGraph generators receive this context (file key, base URL, mode)
    # so they can compute metadata dynamically for gallery cards, social previews, and other modes.
    opengraph = resolve_opengraph_metadata(
        notebook_path,
        context=OpenGraphContext(
            filepath=notebook_path,
            file_key=file_key,
            base_url=app_state.base_url,
            mode=app_state.mode.value,
        ),
    )
    title = opengraph.title or "marimo"
    image = opengraph.image

    validator = PathValidator()
    if image:
        if is_https_url(image):
            return RedirectResponse(
                url=image,
                status_code=307,
                headers={"Cache-Control": "max-age=3600"},
            )

        rel_path = Path(image)
        if not rel_path.is_absolute():
            # Resolve __marimo__/ relative paths against the
            # (potentially relocated) marimo output directory.
            parts = rel_path.parts
            if parts and parts[0] == MARIMO_DIR_NAME:
                file_path = normalize_path(marimo_dir / Path(*parts[1:]))
            else:
                file_path = normalize_path(notebook_dir / rel_path)
            # Only allow serving from the notebook's __marimo__ directory.
            try:
                if file_path.is_file():
                    validator.validate_inside_directory(marimo_dir, file_path)
                    return FileResponse(
                        file_path,
                        headers={"Cache-Control": "max-age=3600"},
                    )
            except HTTPException:
                # Treat invalid paths as a miss; fall back to placeholder.
                pass

    placeholder = DEFAULT_OPENGRAPH_PLACEHOLDER_IMAGE_GENERATOR(title)
    return Response(
        content=placeholder.content,
        media_type=placeholder.media_type,
        # Avoid caching placeholders so newly-generated screenshots show up immediately on refresh.
        headers={"Cache-Control": "no-store"},
    )


async def _fetch_index_html_from_url(asset_url: str) -> str:
    """Fetch index.html from the given asset URL."""
    from marimo._utils import requests
    from marimo._version import __version__

    # Replace {version} placeholder if present
    if "{version}" in asset_url:
        asset_url = asset_url.replace("{version}", __version__)

    # Construct the full URL to index.html
    # Remove trailing slash if present
    asset_url = asset_url.rstrip("/")
    index_url = f"{asset_url}/index.html"

    try:
        LOGGER.debug("Fetching index.html from: %s", index_url)
        response = requests.get(index_url)
        response.raise_for_status()
        return response.text()
    except Exception as e:
        LOGGER.error("Failed to fetch index.html from %s: %s", index_url, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch index.html from asset_url: {e}",
        ) from e


@router.get("/")
async def index(request: Request) -> Response:
    # Manual auth guard instead of `@requires(redirect=...)` so the
    # Location is relative — see `_login_redirect` for the reasoning.
    if not has_required_scope(request, ["read"]):
        return _login_redirect(request)

    # Auth has already passed at this point — either via the session cookie
    # or by validating `access_token` in the query string (which also set
    # the cookie). If the token is still in the URL, redirect to strip it
    # before serving HTML. The Set-Cookie header rides the 303 response, so
    # the browser lands on a clean URL with an authenticated session.
    if TOKEN_QUERY_PARAM in request.query_params:
        return _strip_access_token_redirect(request)

    app_state = AppState(request)
    index_html = root / "index.html"

    file_key_from_query = app_state.query_params(FILE_QUERY_PARAM_KEY)
    file_key = (
        file_key_from_query
        or app_state.session_manager.workspace.get_unique_file_key()
    )

    # Try local index.html first, fallback to asset_url if local file doesn't exist
    if index_html.exists():
        html = index_html.read_text()
    elif app_state.asset_url:
        LOGGER.info(
            "Local index.html not found, fetching from asset_url: %s",
            app_state.asset_url,
        )
        html = await _fetch_index_html_from_url(app_state.asset_url)
    else:
        raise HTTPException(
            status_code=500,
            detail=_missing_index_html_detail(),
        )

    if not file_key:
        # We don't know which file to use, so we need to render a homepage
        LOGGER.debug("No file key provided, serving homepage")
        html = home_page_template(
            html=html,
            base_url=app_state.base_url,
            user_config=app_state.config_manager.get_user_config(),
            config_overrides=app_state.config_manager.get_config_overrides(),
            server_token=app_state.skew_protection_token,
            mode=app_state.mode,
            asset_url=app_state.asset_url,
        )
    else:
        config_manager = app_state.config_manager_at_file(file_key)

        # We have a file key, so we can render the app with the file
        LOGGER.debug(f"File key provided: {file_key}")
        app_manager = app_state.session_manager.app_manager(file_key)
        app_config = app_manager.app.config
        absolute_filepath = app_manager.filename

        # Pre-compute notebook snapshot for faster initial render
        # Only in EDIT + SandboxMode.MULTI where each notebook gets its own IPC
        # kernel.
        notebook_snapshot = None
        if (
            app_state.session_manager.sandbox_mode is SandboxMode.MULTI
            and app_state.mode == SessionMode.EDIT
            and app_manager.filename
        ):
            from marimo._convert.converters import MarimoConvert

            filepath = AsyncPath(app_manager.filename)
            if await filepath.exists():
                try:
                    content = await filepath.read_text(encoding="utf-8")
                    notebook_snapshot = MarimoConvert.from_py(
                        content
                    ).to_notebook_v1()
                except Exception:
                    LOGGER.debug("Failed to pre-compute notebook snapshot")

        filename = app_manager.filename
        directory = app_state.session_manager.workspace.directory
        lsp_workspace = _resolve_lsp_workspace(filename, directory)

        # Make filename relative to file router's directory if possible
        if filename and directory:
            try:
                filename = str(Path(filename).relative_to(directory))
            except ValueError:
                pass  # Keep absolute if not under directory

        html = notebook_page_template(
            html=html,
            base_url=app_state.base_url,
            user_config=config_manager.get_user_config(),
            config_overrides=config_manager.get_config_overrides(),
            server_token=app_state.skew_protection_token,
            app_config=app_config,
            filename=filename,
            filepath=absolute_filepath,
            lsp_workspace=lsp_workspace,
            mode=app_state.mode,
            notebook_snapshot=notebook_snapshot,
            runtime_config=[{"url": app_state.remote_url}]
            if app_state.remote_url
            else None,
            asset_url=app_state.asset_url,
            html_head=app_state.html_head,
        )

        # Inject service worker registration with the notebook ID
        html = _inject_service_worker(html, file_key)

    return HTMLResponse(html, headers=_HTML_SECURITY_HEADERS)


DEFAULT_NOTEBOOK_NAME = "__marimo_notebook__.py"


class LspWorkspace(TypedDict):
    rootUri: str
    documentUri: str


def _resolve_lsp_workspace(
    filename: str | None, directory: str | None
) -> LspWorkspace:
    directory_path = Path(directory or ".").absolute()

    if filename:
        document_path = Path(filename)
        if not document_path.is_absolute():
            document_path = directory_path.joinpath(filename)
        start_path = document_path.parent
    else:
        document_path = directory_path.joinpath(DEFAULT_NOTEBOOK_NAME)
        start_path = directory_path

    if pyproject_path := find_nearest_pyproject_toml(start_path):
        root_path = pyproject_path.parent
    else:
        root_path = directory_path if directory else start_path

    return {
        "rootUri": root_path.as_uri(),
        "documentUri": document_path.as_uri(),
    }


def _inject_service_worker(html: str, file_key: str) -> str:
    return inject_script(
        html,
        # Register service worker with the notebook ID
        # Potentially update the service worker and send the notebook ID again.
        f"""
            if ('serviceWorker' in navigator) {{
                const notebookId = '{uri_encode_component(file_key)}';
                function sendNotebookId(registration) {{
                    if (registration.active) {{
                        registration.active.postMessage({{ notebookId }});
                        return;
                    }}
                    const worker = registration.installing || registration.waiting;
                    if (worker) {{
                        worker.addEventListener('statechange', function() {{
                            if (worker.state === 'activated') {{
                                registration.active.postMessage({{ notebookId }});
                            }}
                        }});
                    }}
                }}
                navigator.serviceWorker.register('./public-files-sw.js?v=2')
                    .then(function(registration) {{
                        sendNotebookId(registration);
                    }})
                    .catch(function(error) {{
                        console.error('Error registering service worker:', error);
                    }});
                navigator.serviceWorker.ready
                    .then(function(registration) {{
                        registration.update().then(function() {{ sendNotebookId(registration); }});
                    }})
                    .catch(function(error) {{
                        console.error('Error updating service worker:', error);
                    }});
            }} else {{
                console.warn(
                    '[marimo] Service workers are not supported at this URL. Displaying files from the /public/ directory may be disabled. ' +
                    'To fix this, enable service workers by using a secure connection (https) or localhost.'
                );
            }}
            """,
    )


STATIC_FILES = [
    r"(favicon\.ico)",
    r"(manifest\.json)",
    r"(android-chrome-(192x192|512x512)\.png)",
    r"(apple-touch-icon\.png)",
    r"(logo\.png)",
]


@router.get("/@file/{filename_and_length:path}")
def virtual_file(
    request: Request,
) -> Response:
    """
    parameters:
        - in: path
          name: filename_and_length
          required: true
          schema:
            type: string
          description: The filename and byte length of the virtual file
    responses:
        200:
            description: Get a virtual file
            content:
                application/octet-stream:
                    schema:
                        type: string
        404:
            description: Invalid virtual file request
        404:
            description: Invalid byte length in virtual file request
    """
    # Auth is normally required via `@requires("read")`, but can be bypassed
    # with the `_MARIMO_DISABLE_AUTH_ON_VIRTUAL_FILES` env var for
    # sandboxed/embedded deployments where virtual file URLs must be
    # fetched without session auth.
    if not GLOBAL_SETTINGS.DISABLE_AUTH_ON_VIRTUAL_FILES:
        if not has_required_scope(request, ["read"]):
            raise HTTPException(status_code=403)

    filename_and_length = request.path_params["filename_and_length"]

    LOGGER.debug("Getting virtual file: %s", filename_and_length)
    if filename_and_length == EMPTY_VIRTUAL_FILE.filename:
        return Response(content=b"", media_type="application/octet-stream")
    if "-" not in filename_and_length:
        raise HTTPException(
            status_code=404,
            detail="Invalid virtual file request",
        )

    byte_length, filename = filename_and_length.split("-", 1)
    if not byte_length.isdigit():
        raise HTTPException(
            status_code=404,
            detail="Invalid byte length in virtual file request",
        )

    chunks = read_virtual_file_chunked(filename, int(byte_length))
    mimetype, _ = mimetypes.guess_type(filename)
    headers = {
        "Cache-Control": "max-age=86400",
    }
    # When ?download=1 is set, force a save dialog. This bypasses cases
    # where <a download> is ignored (e.g., sandboxed iframes without
    # allow-downloads, or some Permissions-Policy configurations).
    if request.query_params.get("download") == "1":
        from marimo._convert.common.filename import make_download_headers

        download_filename = request.query_params.get("filename") or filename
        headers.update(make_download_headers(download_filename))
    # Do NOT set Content-Length here. StreamingResponse with an explicit
    # Content-Length causes h11 LocalProtocolError ("Too little data for
    # declared Content-Length") for large files. Omitting it lets h11 use
    # chunked transfer encoding instead. See #8917.
    return StreamingResponse(
        content=chunks,
        media_type=mimetype,
        headers=headers,
    )


@router.get("/public-files-sw.js")
async def public_files_service_worker(request: Request) -> Response:
    """
    Service worker that adds the notebook ID to the request headers.
    """
    del request
    return Response(
        content="""
        let notebookIdPromise = new Promise((resolve) => {
            self.addEventListener('message', (event) => {
                if (event.data.notebookId) {
                    resolve(event.data.notebookId);
                }
            });
        });

        self.addEventListener('fetch', function(event) {
            if (event.request.url.includes('/public/')) {
                event.respondWith(
                    notebookIdPromise.then(notebookId => {
                        return fetch(event.request.url, {
                            headers: {
                                'X-Notebook-Id': notebookId
                            }
                        });
                    })
                );
            }
        });
        """,
        media_type="application/javascript",
    )


@router.get("/public/{filepath:path}")
@requires("read")
async def serve_public_file(request: Request) -> Response:
    """Serve files from the notebook's directory under /public/"""
    app_state = AppState(request)
    filepath = str(request.path_params["filepath"])
    # Get notebook ID from header
    notebook_id = request.headers.get("X-Notebook-Id")
    if notebook_id:
        # Decode notebook ID
        notebook_id = uri_decode_component(notebook_id)
        app_manager = app_state.session_manager.app_manager(notebook_id)
        if app_manager.filename:
            notebook_dir = Path(app_manager.filename).parent
        else:
            notebook_dir = Path.cwd()
        public_dir = notebook_dir / "public"
        file_path = public_dir / filepath

        # Security check: ensure file is inside public directory.
        # validate_inside_directory preserves symlinks, so also verify the
        # resolved target stays within public_dir to avoid symlinks in
        # public/ pointing at files outside the notebook's public directory.
        try:
            PathValidator().validate_inside_directory(public_dir, file_path)
        except HTTPException:
            return Response(status_code=403, content="Access denied")

        try:
            resolved_file = file_path.resolve(strict=True)
            resolved_public = public_dir.resolve(strict=True)
            resolved_file.relative_to(resolved_public)
        except (OSError, ValueError):
            raise HTTPException(
                status_code=404, detail="File not found"
            ) from None

        if resolved_file.is_file():
            return FileResponse(resolved_file)

    raise HTTPException(status_code=404, detail="File not found")


# Catch all for serving static files
@router.get("/{path:path}")
async def serve_static(request: Request) -> FileResponse:
    path = str(request.path_params["path"])
    if any(re.fullmatch(pattern, path) for pattern in STATIC_FILES):
        file_path = Path(path)
        try:
            PathValidator().validate_inside_directory(root, file_path)
        except Exception:
            raise HTTPException(status_code=404, detail="Not Found") from None
        resolved = root / path
        if not resolved.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(resolved)

    raise HTTPException(status_code=404, detail="Not Found")
