# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from marimo._runtime.packages.package_manager import PackageManager
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from unittest.mock import Mock

    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@pytest.fixture
def mock_package_manager(monkeypatch: pytest.MonkeyPatch) -> PackageManager:
    mock_manager = MagicMock(spec=PackageManager)
    mock_manager.install = AsyncMock(return_value=True)
    mock_manager.uninstall = AsyncMock(return_value=True)
    mock_manager.list_packages = MagicMock(
        return_value=["package1", "package2"]
    )

    def mock_get_package_manager(request: Any) -> PackageManager:
        del request
        return mock_manager

    monkeypatch.setattr(
        "marimo._server.api.endpoints.packages._get_package_manager",
        mock_get_package_manager,
    )
    return mock_manager


def test_add_package(client: TestClient, mock_package_manager: Mock) -> None:
    assert isinstance(mock_package_manager, MagicMock)
    response = client.post(
        "/api/packages/add",
        headers=HEADERS,
        json={"package": "test-package"},
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "error": None}
    mock_package_manager.install.assert_called_once_with(
        "test-package", version=None, upgrade=False
    )


def test_add_package_no_name(
    client: TestClient, mock_package_manager: Mock
) -> None:
    with pytest.raises(TypeError):
        client.post(
            "/api/packages/add",
            headers=HEADERS,
            json={},
        )
    mock_package_manager.install.assert_not_called()


def test_remove_package(
    client: TestClient, mock_package_manager: Mock
) -> None:
    response = client.post(
        "/api/packages/remove",
        headers=HEADERS,
        json={"package": "test-package"},
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "error": None}
    mock_package_manager.uninstall.assert_called_once_with("test-package")


def test_remove_package_no_name(
    client: TestClient, mock_package_manager: Mock
) -> None:
    with pytest.raises(TypeError):
        client.post(
            "/api/packages/remove",
            headers=HEADERS,
            json={},
        )
    mock_package_manager.uninstall.assert_not_called()


def test_list_packages(client: TestClient, mock_package_manager: Mock) -> None:
    response = client.get(
        "/api/packages/list",
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {
        "packages": ["package1", "package2"],
    }
    mock_package_manager.list_packages.assert_called_once()


def test_add_package_failure(
    client: TestClient, mock_package_manager: Mock
) -> None:
    mock_package_manager.install.return_value = False
    response = client.post(
        "/api/packages/add",
        headers=HEADERS,
        json={"package": "test-package"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "error": "Failed to install test-package. See terminal for error logs.",  # noqa: E501
    }


def test_remove_package_failure(
    client: TestClient, mock_package_manager: Mock
) -> None:
    mock_package_manager.uninstall.return_value = False
    response = client.post(
        "/api/packages/remove",
        headers=HEADERS,
        json={"package": "test-package"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "error": "Failed to uninstall test-package. See terminal for error logs.",  # noqa: E501
    }


def test_add_package_with_upgrade(
    client: TestClient, mock_package_manager: Mock
) -> None:
    assert isinstance(mock_package_manager, MagicMock)
    response = client.post(
        "/api/packages/add",
        headers=HEADERS,
        json={"package": "test-package", "upgrade": True},
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "error": None}
    mock_package_manager.install.assert_called_once_with(
        "test-package", version=None, upgrade=True
    )


def test_add_package_without_upgrade(
    client: TestClient, mock_package_manager: Mock
) -> None:
    assert isinstance(mock_package_manager, MagicMock)
    response = client.post(
        "/api/packages/add",
        headers=HEADERS,
        json={"package": "test-package", "upgrade": False},
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "error": None}
    mock_package_manager.install.assert_called_once_with(
        "test-package", version=None, upgrade=False
    )
