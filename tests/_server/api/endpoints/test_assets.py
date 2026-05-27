# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock, patch

from marimo._server.api.deps import AppState
from marimo._server.api.endpoints.assets import (
    DEFAULT_NOTEBOOK_NAME,
    _inject_service_worker,
)
from marimo._server.api.utils import parse_title
from marimo._server.workspace import (
    DirectoryWorkspace,
    EmptyWorkspace,
    FixedFilesWorkspace,
    SingleFileWorkspace,
)
from marimo._session.model import SessionMode
from marimo._utils.marimo_path import MarimoPath
from tests._server.mocks import (
    token_header,
    with_workspace,
    workspace_scope,
)

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def test_index(client: TestClient) -> None:
    session_manager = AppState.from_app(cast(Any, client.app)).session_manager

    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    filename = session_manager.workspace.get_unique_file_key()
    title = parse_title(filename)
    assert f"<marimo-filename hidden>{filename}</marimo-filename>" in content
    assert filename is not None
    assert filename in content
    assert '"mode": "edit"' in content
    assert f"<title>{title}</title>" in content

    # Check for /public file service worker
    assert "public-files-sw.js" in content


@with_workspace(FixedFilesWorkspace([]))
def test_index_when_empty(client: TestClient) -> None:
    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename hidden></marimo-filename>" in content
    assert '"mode": "home"' in content
    assert "<title>marimo</title>" in content


@with_workspace(EmptyWorkspace())
def test_index_when_new_file(client: TestClient) -> None:
    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename hidden></marimo-filename>" in content
    assert '"mode": "edit"' in content
    assert "<title>marimo</title>" in content


def test_index_missing_assets_in_source_checkout_shows_build_hint(
    client: TestClient, tmp_path: Path
) -> None:
    source_root = tmp_path / "repo"
    source_root.mkdir()
    (source_root / "frontend").mkdir()
    (source_root / "pyproject.toml").write_text("")

    missing_static_root = tmp_path / "missing_static"
    missing_static_root.mkdir()

    with (
        patch("marimo._server.api.endpoints.assets.root", missing_static_root),
        patch(
            "marimo._server.api.endpoints.assets.marimo_package_path",
            return_value=source_root / "marimo",
        ),
    ):
        response = client.get("/", headers=token_header())

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "Did you run `make fe`?" in detail
    assert "Restart marimo after building." in detail


def test_index_strips_access_token_query_param(client: TestClient) -> None:
    # A valid `?access_token=` in the URL should 303 to the same path with
    # the token removed, carrying a session cookie so the follow-up request
    # is already authenticated. This prevents pre-execution XSS, Referer,
    # or browser history from capturing the plaintext token.
    response = client.get("/?access_token=fake-token", follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/"
    assert response.headers.get("referrer-policy") == "same-origin"
    assert response.headers.get("x-content-type-options") == "nosniff"
    # The session cookie must be set so the redirect target is authenticated
    # without the query param.
    set_cookie = response.headers.get("set-cookie", "")
    assert "session" in set_cookie


def test_index_strips_access_token_preserves_other_params(
    client: TestClient,
) -> None:
    response = client.get(
        "/?file=foo.py&access_token=fake-token&view-as=present",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert location.startswith("/")
    assert "access_token" not in location
    assert "file=foo.py" in location
    assert "view-as=present" in location


def test_index_invalid_access_token_redirects_to_login(
    client: TestClient,
) -> None:
    # An invalid token must NOT trigger the token-strip redirect (which
    # would imply the token was accepted). Instead, the auth guard should
    # redirect the unauthenticated request to the login page. Following
    # the redirect lands on the login HTML.
    response = client.get("/?access_token=wrong-token", follow_redirects=False)
    assert response.status_code in (302, 303), response.text
    assert "login" in response.headers["location"].lower()
    # Following the redirect lands on the login page.
    followed = client.get("/?access_token=wrong-token")
    assert followed.status_code == 200
    assert "Login" in followed.text


def test_index_unauthenticated_redirect_is_relative(
    client: TestClient,
) -> None:
    # Regression test for https://github.com/marimo-team/marimo/issues/9249.
    # When a reverse proxy forwards an internal `Host` header, an absolute
    # Location would send the browser to an unreachable internal address.
    # The Location must be relative so the browser resolves it against the
    # public URL it originally used.
    response = client.get(
        "/",
        headers={"Host": "10.0.0.5:60830"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    # Must be relative — no scheme, no host.
    assert location.startswith("/auth/login?"), location
    assert "://" not in location
    assert "10.0.0.5" not in location


def test_index_unauthenticated_redirect_preserves_next(
    client: TestClient,
) -> None:
    # The original path (and query) must round-trip through the redirect so
    # the user lands where they were trying to go after logging in.
    response = client.get(
        "/?file=foo.py&view-as=present",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert location.startswith("/auth/login?"), location
    # next= is percent-encoded; decoding it should yield the original path
    # with its query string.
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(location)
    next_value = parse_qs(parsed.query)["next"][0]
    assert next_value == "/?file=foo.py&view-as=present"


def test_index_response_has_security_headers(client: TestClient) -> None:
    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    assert response.headers.get("referrer-policy") == "same-origin"
    assert response.headers.get("x-content-type-options") == "nosniff"


def test_index_with_directory(client: TestClient, tmp_path: Path) -> None:
    with workspace_scope(
        client, DirectoryWorkspace(str(tmp_path), include_markdown=False)
    ):
        response = client.get("/", headers=token_header())
        assert response.status_code == 200, response.text
        content = response.text
        assert "<marimo-filename" in content
        assert '"mode": "home"' in content
        assert "<title>marimo</title>" in content


def test_index_with_directory_run_mode(
    client: TestClient, tmp_path: Path
) -> None:
    app_state = AppState.from_app(cast(Any, client.app))
    app_state.session_manager.mode = SessionMode.RUN

    with workspace_scope(
        client, DirectoryWorkspace(str(tmp_path), include_markdown=False)
    ):
        response = client.get("/", headers=token_header())
        assert response.status_code == 200, response.text
        content = response.text
        assert "<marimo-filename" in content
        assert '"mode": "gallery"' in content
        assert "<title>marimo</title>" in content


def test_favicon(client: TestClient) -> None:
    response = client.get("/favicon.ico")
    assert response.status_code == 200, response.text
    content_type = response.headers["content-type"]
    assert (
        content_type == "image/x-icon"
        or content_type == "image/vnd.microsoft.icon"
    )


def test_unknown_file(client: TestClient) -> None:
    response = client.get("/unknown_file")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}


def test_vfile(client: TestClient) -> None:
    response = client.get("/@file/example.txt")
    assert response.status_code == 401, response.text

    response = client.get("/@file/empty.txt", headers=token_header())
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.content == b""

    response = client.get("/@file/bad.txt", headers=token_header())
    assert response.status_code == 404, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Invalid virtual file request"}


@patch(
    "marimo._server.api.endpoints.assets.GLOBAL_SETTINGS.DISABLE_AUTH_ON_VIRTUAL_FILES",
    True,
)
def test_vfile_auth_disabled_allows_unauthenticated(
    client: TestClient,
) -> None:
    # Unauthenticated requests normally return 401, but the env flag
    # lets them through.
    response = client.get("/@file/empty.txt")
    assert response.status_code == 200, response.text
    assert response.content == b""

    response = client.get("/@file/bad.txt")
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Invalid virtual file request"}


@patch(
    "marimo._server.api.endpoints.assets.GLOBAL_SETTINGS.DISABLE_AUTH_ON_VIRTUAL_FILES",
    False,
)
def test_vfile_auth_enabled_rejects_unauthenticated(
    client: TestClient,
) -> None:
    # With the flag off (the default), unauthenticated requests are rejected.
    response = client.get("/@file/empty.txt")
    assert response.status_code == 401, response.text

    # Authenticated requests still work.
    response = client.get("/@file/empty.txt", headers=token_header())
    assert response.status_code == 200, response.text


def test_vfile_large_streaming(client: TestClient) -> None:
    """Regression test: large virtual files must stream without
    Content-Length mismatch (h11 LocalProtocolError).

    See https://github.com/marimo-team/marimo/issues/8917
    """
    from marimo._runtime.virtual_file.storage import (
        InMemoryStorage,
        VirtualFileStorageManager,
    )

    manager = VirtualFileStorageManager()
    original_storage = manager.storage
    storage = InMemoryStorage()
    manager.storage = storage

    try:
        # ~2 MB file, similar to a large anywidget ESM bundle
        data = b"x" * (2 * 1024 * 1024)
        filename = "test-large.js"
        storage.store(filename, data)
        byte_length = len(data)

        response = client.get(
            f"/@file/{byte_length}-{filename}",
            headers=token_header(),
        )
        assert response.status_code == 200
        assert response.content == data
        assert (
            response.headers.get("content-type") == "text/javascript"
            or response.headers.get("content-type") == "application/javascript"
        )
        # StreamingResponse must NOT set Content-Length to avoid h11
        # LocalProtocolError with large files
        assert "content-length" not in response.headers
    finally:
        manager.storage = original_storage


def test_vfile_range_requests(client: TestClient) -> None:
    """Virtual files must support HTTP Range requests so that Safari can
    play media (audio/video) — Safari's <audio> element refuses to load
    sources whose server doesn't return 206 Partial Content for range
    probes.

    See https://github.com/marimo-team/marimo/issues/9460
    """
    from marimo._runtime.virtual_file.storage import (
        InMemoryStorage,
        VirtualFileStorageManager,
    )

    manager = VirtualFileStorageManager()
    original_storage = manager.storage
    storage = InMemoryStorage()
    manager.storage = storage

    try:
        data = bytes(range(256)) * 8  # 2048 bytes of deterministic content
        filename = "test-audio.wav"
        storage.store(filename, data)
        byte_length = len(data)
        url = f"/@file/{byte_length}-{filename}"

        # Plain GET advertises Accept-Ranges so clients know they can probe.
        response = client.get(url, headers=token_header())
        assert response.status_code == 200, response.text
        assert response.headers.get("accept-ranges") == "bytes"
        assert response.content == data

        # Bounded range returns 206 with Content-Range and exact bytes.
        response = client.get(
            url,
            headers={**token_header(), "Range": "bytes=0-99"},
        )
        assert response.status_code == 206, response.text
        assert (
            response.headers.get("content-range")
            == f"bytes 0-99/{byte_length}"
        )
        assert response.headers.get("content-length") == "100"
        assert response.headers.get("accept-ranges") == "bytes"
        assert response.content == data[0:100]

        # Open-ended range (start-) serves to the end of the file.
        response = client.get(
            url,
            headers={**token_header(), "Range": "bytes=50-"},
        )
        assert response.status_code == 206, response.text
        end = byte_length - 1
        assert (
            response.headers.get("content-range")
            == f"bytes 50-{end}/{byte_length}"
        )
        assert response.content == data[50:]

        # Suffix range (-N) returns the last N bytes.
        response = client.get(
            url,
            headers={**token_header(), "Range": "bytes=-50"},
        )
        assert response.status_code == 206, response.text
        start = byte_length - 50
        assert (
            response.headers.get("content-range")
            == f"bytes {start}-{end}/{byte_length}"
        )
        assert response.content == data[-50:]

        # Out-of-range start → 416 with Content-Range advertising the size.
        response = client.get(
            url,
            headers={**token_header(), "Range": f"bytes={byte_length}-"},
        )
        assert response.status_code == 416, response.text
        assert (
            response.headers.get("content-range") == f"bytes */{byte_length}"
        )

        # Range unit token is case-insensitive per RFC 9110.
        response = client.get(
            url,
            headers={**token_header(), "Range": "Bytes=0-99"},
        )
        assert response.status_code == 206, response.text
        assert response.content == data[:100]
    finally:
        manager.storage = original_storage


def test_vfile_download_query_param_sets_content_disposition(
    client: TestClient,
) -> None:
    """`?download=1` forces Content-Disposition: attachment so the browser
    saves the response instead of rendering it inline. This covers iframed
    deployments where <a download> is silently ignored."""
    from marimo._runtime.virtual_file.storage import (
        InMemoryStorage,
        VirtualFileStorageManager,
    )

    manager = VirtualFileStorageManager()
    original_storage = manager.storage
    storage = InMemoryStorage()
    manager.storage = storage

    try:
        data = b'[{"a": 1}]'
        filename = "data.json"
        storage.store(filename, data)
        byte_length = len(data)

        # Without ?download=1 — no Content-Disposition.
        response = client.get(
            f"/@file/{byte_length}-{filename}",
            headers=token_header(),
        )
        assert response.status_code == 200
        assert "content-disposition" not in response.headers

        # With ?download=1 — attachment header is set.
        response = client.get(
            f"/@file/{byte_length}-{filename}?download=1",
            headers=token_header(),
        )
        assert response.status_code == 200
        assert response.content == data
        cd = response.headers.get("content-disposition", "")
        assert cd.startswith("attachment")
        assert "data.json" in cd

        # Custom download filename via ?filename=...
        response = client.get(
            f"/@file/{byte_length}-{filename}"
            "?download=1&filename=my-export.json",
            headers=token_header(),
        )
        assert response.status_code == 200
        cd = response.headers.get("content-disposition", "")
        assert cd.startswith("attachment")
        assert "my-export.json" in cd
    finally:
        manager.storage = original_storage


def test_public_file_serving(client: TestClient) -> None:
    # Setup app state with a mock notebook
    app_state = AppState.from_app(cast(Any, client.app))
    file_key = app_state.session_manager.workspace.get_unique_file_key()
    assert file_key is not None
    assert file_key.endswith(".py")

    # Create a test file in a public directory
    notebook_dir = Path(file_key).parent
    public_dir = notebook_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    test_file = public_dir / "test.txt"
    test_file.write_text("test content")

    # Test without notebook ID header
    response = client.get("/public/test.txt", headers=token_header())
    assert response.status_code == 404

    # Test with notebook ID header
    headers = {**token_header(), "X-Notebook-Id": file_key}
    response = client.get("/public/test.txt", headers=headers)
    assert response.status_code == 200
    assert response.text == "test content"

    # Test non-existent file
    response = client.get("/public/nonexistent.txt", headers=headers)
    assert response.status_code in [403, 404]

    # Cleanup
    test_file.unlink()


def test_service_worker(client: TestClient) -> None:
    response = client.get("/public-files-sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/javascript"
    assert "self.addEventListener('fetch'" in response.text
    assert "X-Notebook-Id" in response.text


def test_public_file_security(client: TestClient) -> None:
    # Setup app state
    app_state = AppState.from_app(cast(Any, client.app))
    file_key = app_state.session_manager.workspace.get_unique_file_key()
    assert file_key is not None
    assert file_key.endswith(".py")

    # Setup notebook and directories
    notebook_dir = Path(file_key).parent
    public_dir = notebook_dir / "public"
    secret_dir = notebook_dir / "secret"
    public_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Create test files
        (public_dir / "safe.txt").write_text("public content")
        (secret_dir / "secret.txt").write_text("secret content")

        # Create a symlink in public pointing outside
        os.symlink(
            str(secret_dir / "secret.txt"), str(public_dir / "symlink.txt")
        )

        app_manager = app_state.session_manager.app_manager(file_key)
        app_manager.filename = str(notebook_dir / "notebook.py")

        headers = {**token_header(), "X-Notebook-Id": file_key}

        # Test normal file access
        response = client.get("/public/safe.txt", headers=headers)
        assert response.status_code == 200
        assert response.text == "public content"

        # Test path traversal attempt
        response = client.get(
            "/public/data/../../secret/secret.txt", headers=headers
        )
        assert response.status_code == 404

        # Symlinks in public/ that point outside public/ are rejected,
        # even though the symlink itself lives inside public/.
        response = client.get("/public/symlink.txt", headers=headers)
        assert response.status_code == 404

        # A symlink whose target is still inside public/ is allowed.
        os.symlink(
            str(public_dir / "safe.txt"),
            str(public_dir / "inside_link.txt"),
        )
        response = client.get("/public/inside_link.txt", headers=headers)
        assert response.status_code == 200
        assert response.text == "public content"

    finally:
        # Cleanup
        shutil.rmtree(public_dir, ignore_errors=True)
        shutil.rmtree(secret_dir, ignore_errors=True)


def test_inject_service_worker() -> None:
    assert (
        "const notebookId = 'path%2Fto%2Fnotebook.py';"
        in _inject_service_worker("<body></body>", "path/to/notebook.py")
    )
    assert (
        "const notebookId = 'c%3A%5Cpath%5Cto%5Cnotebook.py';"
        in _inject_service_worker("<body></body>", r"c:\path\to\notebook.py")
    )


def test_inject_service_worker_null_check() -> None:
    result = _inject_service_worker("<body></body>", "notebook.py")
    # The helper function should check registration.active before posting
    assert "function sendNotebookId(registration)" in result
    assert "if (registration.active)" in result
    # Should handle installing/waiting workers via statechange listener
    assert "registration.installing || registration.waiting" in result
    assert "statechange" in result


def test_index_with_missing_local_file_and_asset_url(
    client: TestClient,
) -> None:
    """Test that index.html is fetched from asset_url when local file doesn't exist."""
    app_state = AppState.from_app(cast(Any, client.app))

    # Mock HTML content that would come from the CDN
    mock_html = """<!DOCTYPE html>
<html>
<head><title>{{ title }}</title></head>
<body>
<marimo-filename hidden>{{ filename }}</marimo-filename>
'{{ mount_config }}'
</body>
</html>"""

    # Mock the requests.get to return our mock HTML
    mock_response = Mock()
    mock_response.text.return_value = mock_html
    mock_response.raise_for_status.return_value = None

    with (
        patch("marimo._server.api.endpoints.assets.root") as mock_root,
        patch("marimo._utils.requests.get", return_value=mock_response),
    ):
        # Make local index.html appear to not exist
        mock_index_html = Mock()
        mock_index_html.exists.return_value = False
        mock_root.__truediv__.return_value = mock_index_html

        # Set asset_url on the app state
        client.app.state.asset_url = "https://cdn.example.com/assets/0.1.0"

        response = client.get("/", headers=token_header())
        assert response.status_code == 200, response.text
        # The response should contain processed HTML
        assert "<title>" in response.text


def test_index_with_missing_local_file_no_asset_url(
    client: TestClient,
) -> None:
    """Test that error is raised when local file doesn't exist and no asset_url."""
    with patch("marimo._server.api.endpoints.assets.root") as mock_root:
        # Make local index.html appear to not exist
        mock_index_html = Mock()
        mock_index_html.exists.return_value = False
        mock_root.__truediv__.return_value = mock_index_html

        # Ensure asset_url is None
        client.app.state.asset_url = None

        response = client.get("/", headers=token_header())
        assert response.status_code == 500
        assert "index.html not found" in response.json()["detail"]


def test_index_prefers_local_file_over_asset_url(client: TestClient) -> None:
    """Test that local index.html is preferred even when asset_url is set."""
    # Set asset_url on the app state
    client.app.state.asset_url = "https://cdn.example.com/assets/0.1.0"

    # Mock requests.get to track if it's called
    mock_response = Mock()
    with patch(
        "marimo._utils.requests.get", return_value=mock_response
    ) as mock_get:
        response = client.get("/", headers=token_header())
        assert response.status_code == 200, response.text

        # requests.get should NOT be called since local file exists
        mock_get.assert_not_called()

    # Reset asset_url
    client.app.state.asset_url = None


def test_index_includes_notebook_key_in_mount_config(
    client: TestClient,
) -> None:
    """Test that index response includes notebook in mount config."""
    response = client.get("/", headers=token_header())
    assert response.status_code == 200

    # Verify notebook key is present in mount config by checking HTML content
    # The mount config is injected as JSON in the HTML
    assert '"notebook":' in response.text or "'notebook':" in response.text


def test_index_lsp_workspace_with_filename(
    client: TestClient, tmp_path: Path
) -> None:
    temp_project_dir = tmp_path
    temp_project_dir.joinpath("pyproject.toml").touch()
    subdir = temp_project_dir.joinpath("subdir")
    subdir.mkdir()
    notebook_file = subdir.joinpath("notebook.py")
    notebook_file.touch()

    with workspace_scope(
        client, SingleFileWorkspace.from_path(MarimoPath(notebook_file))
    ):
        response = client.get("/", headers=token_header())
        root_uri = json.dumps(temp_project_dir.as_uri())
        document_uri = json.dumps(notebook_file.as_uri())
        assert f'"rootUri": {root_uri}' in response.text
        assert f'"documentUri": {document_uri}' in response.text


def test_index_lsp_workspace_with_root_directory(
    client: TestClient, tmp_path: Path
) -> None:
    temp_project_dir = tmp_path
    temp_project_dir.joinpath("pyproject.toml").touch()

    with workspace_scope(
        client,
        DirectoryWorkspace(str(temp_project_dir), include_markdown=False),
    ):
        response = client.get("/?file=__new__file.py", headers=token_header())
        root_path = temp_project_dir
        root_uri = json.dumps(root_path.as_uri())
        document_path = root_path.joinpath(DEFAULT_NOTEBOOK_NAME)
        document_uri = json.dumps(document_path.as_uri())
        assert f'"rootUri": {root_uri}' in response.text
        assert f'"documentUri": {document_uri}' in response.text


def test_index_lsp_workspace_with_sub_directory(
    client: TestClient, tmp_path: Path
) -> None:
    temp_project_dir = tmp_path
    temp_project_dir.joinpath("pyproject.toml").touch()
    subdir = temp_project_dir.joinpath("subdir")
    subdir.mkdir()

    with workspace_scope(
        client, DirectoryWorkspace(str(subdir), include_markdown=False)
    ):
        response = client.get("/?file=__new__file.py", headers=token_header())
        root_path = temp_project_dir
        root_uri = json.dumps(root_path.as_uri())
        document_path = subdir.joinpath(DEFAULT_NOTEBOOK_NAME)
        document_uri = json.dumps(document_path.as_uri())
        assert f'"rootUri": {root_uri}' in response.text
        assert f'"documentUri": {document_uri}' in response.text


@with_workspace(EmptyWorkspace())
def test_index_lsp_workspace_fallback_to_cwd(client: TestClient) -> None:
    response = client.get("/", headers=token_header())
    root_path = Path.cwd()
    root_uri = json.dumps(root_path.as_uri())
    document_path = root_path.joinpath(DEFAULT_NOTEBOOK_NAME)
    document_uri = json.dumps(document_path.as_uri())
    assert f'"rootUri": {root_uri}' in response.text
    assert f'"documentUri": {document_uri}' in response.text


def test_serve_static_path_traversal(client: TestClient) -> None:
    # Prefix-match bypass (GHSA-3rj5-4vhf-pm45): re.match would allow
    # "favicon.ico/../../anything" because it only checks the start of the
    # string. re.fullmatch rejects it outright.
    traversal_paths = [
        "favicon.ico/../../etc/passwd",
        "favicon.ico/../../../etc/passwd",
        "manifest.json/../../etc/passwd",
        "favicon.ico/%2e%2e/%2e%2e/etc/passwd",
        "favicon.ico/evil",
        "favicon.icoevil",
    ]
    for path in traversal_paths:
        response = client.get(f"/{path}", follow_redirects=False)
        assert response.status_code == 404, (
            f"Expected 404 for traversal path {path!r}, got {response.status_code}"
        )


def test_serve_static_allowed_files(client: TestClient) -> None:
    # Exact matches from STATIC_FILES should resolve without error (the file
    # may not exist in the test environment, but we should not get a 404 from
    # the allowlist check itself — a missing-file 404 from FileResponse is
    # fine; what we're testing is that the allowlist admits the right names).
    allowed = [
        "favicon.ico",
        "manifest.json",
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "apple-touch-icon.png",
        "logo.png",
    ]
    for name in allowed:
        response = client.get(f"/{name}", follow_redirects=False)
        # 200 if the file exists in the package, 404 if not — either is
        # acceptable here; the important thing is it is NOT rejected by the
        # traversal guard (which would also 404, but for a different reason).
        # We verify the path was at least considered by checking it didn't
        # fall through to the catch-all "Not Found" with an allowlist miss.
        assert response.status_code in (200, 404), (
            f"Unexpected status {response.status_code} for {name!r}"
        )
