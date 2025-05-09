from pathlib import Path
from typing import Optional

import pytest
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse

from marimo._server.api.assets import StaticAssetsHandler


@pytest.fixture
def temp_assets_dir(tmp_path: Path) -> Path:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "test.txt").write_text("test content")
    return assets_dir


@pytest.fixture
def mock_url(monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        def __init__(
            self,
            content: bytes,
            status_code: int = 200,
            headers: Optional[dict[str, str]] = None,
        ) -> None:
            self.content = content
            self.status_code = status_code
            self.headers = headers or {"content-type": "text/plain"}

        def text(self) -> str:
            return self.content.decode()

    def mock_get(url: str) -> MockResponse:
        if "not_found" in url:
            return MockResponse(b"", status_code=404)
        return MockResponse(b"test content")

    monkeypatch.setattr("marimo._utils.requests.get", mock_get)


def test_init_with_path(temp_assets_dir: Path) -> None:
    handler = StaticAssetsHandler(temp_assets_dir)
    assert handler.root == temp_assets_dir
    assert not handler.is_url
    assert handler.is_file


def test_init_with_url() -> None:
    handler = StaticAssetsHandler("https://example.com")
    assert handler.root == "https://example.com"
    assert handler.is_url
    assert not handler.is_file


def test_is_symlink(temp_assets_dir: Path) -> None:
    handler = StaticAssetsHandler(temp_assets_dir)
    assert not handler.is_symlink()


@pytest.mark.asyncio
async def test_get_file_from_file(temp_assets_dir: Path) -> None:
    handler = StaticAssetsHandler(temp_assets_dir)
    response = await handler.get("test.txt")
    assert response.status_code == 200
    assert isinstance(response, FileResponse)


@pytest.mark.asyncio
async def test_get_file_from_file_not_found(temp_assets_dir: Path) -> None:
    handler = StaticAssetsHandler(temp_assets_dir)
    with pytest.raises(HTTPException) as exc_info:
        await handler.get("nonexistent.txt")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_file_from_url(mock_url: None) -> None:
    del mock_url
    handler = StaticAssetsHandler("https://example.com")
    response = await handler.get("test.txt")
    assert response.status_code == 200
    assert response.body == b"test content"


@pytest.mark.asyncio
async def test_get_file_from_url_not_found(mock_url: None) -> None:
    del mock_url
    handler = StaticAssetsHandler("https://example.com")
    with pytest.raises(HTTPException) as exc_info:
        await handler.get("not_found.txt")
    assert exc_info.value.status_code == 404


def test_read_file(temp_assets_dir: Path) -> None:
    handler = StaticAssetsHandler(temp_assets_dir)
    content = handler.read("test.txt")
    assert content == "test content"


def test_read_url(mock_url: None) -> None:
    del mock_url
    handler = StaticAssetsHandler("https://example.com")
    content = handler.read("test.txt")
    assert content == "test content"


def test_read_not_configured() -> None:
    handler = StaticAssetsHandler("")
    with pytest.raises(FileNotFoundError):
        handler.read("test.txt")
