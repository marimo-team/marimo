# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import msgspec
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
        "test-package", version=None, upgrade=False, group=None
    )


def test_add_package_no_name(
    client: TestClient, mock_package_manager: Mock
) -> None:
    with pytest.raises(msgspec.ValidationError):
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
    mock_package_manager.uninstall.assert_called_once_with(
        "test-package", group=None
    )


def test_remove_package_no_name(
    client: TestClient, mock_package_manager: Mock
) -> None:
    with pytest.raises(msgspec.ValidationError):
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
        "test-package", version=None, upgrade=True, group=None
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
        "test-package", version=None, upgrade=False, group=None
    )


def test_add_package_with_complex_version_spec(
    client: TestClient, mock_package_manager: Mock
) -> None:
    """Test add_package with complex version specifications."""
    response = client.post(
        "/api/packages/add",
        headers=HEADERS,
        json={"package": "package>=1.0.0,<2.0.0"},
    )
    assert response.status_code == 200
    mock_package_manager.install.assert_called_once()


def test_add_package_with_empty_string(
    client: TestClient, mock_package_manager: Mock
) -> None:
    """Test add_package with empty package name."""
    response = client.post(
        "/api/packages/add",
        headers=HEADERS,
        json={"package": ""},
    )
    assert response.status_code in [200, 400, 422]
    mock_package_manager.install.assert_called_once()


def test_remove_package_with_empty_string(
    client: TestClient, mock_package_manager: Mock
) -> None:
    """Test remove_package with empty package name."""
    response = client.post(
        "/api/packages/remove",
        headers=HEADERS,
        json={"package": ""},
    )
    assert response.status_code in [200, 400, 422]
    mock_package_manager.uninstall.assert_called_once_with("", group=None)


@pytest.fixture
def mock_package_manager_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> PackageManager:
    """Mock package manager that is not installed."""
    mock_manager = MagicMock(spec=PackageManager)
    mock_manager.is_manager_installed.return_value = False
    mock_manager.name = "test-manager"
    mock_manager.docs_url = "https://example.com/docs"
    mock_manager.alert_not_installed = MagicMock()

    def mock_get_package_manager(request: Any) -> PackageManager:
        del request
        return mock_manager

    monkeypatch.setattr(
        "marimo._server.api.endpoints.packages._get_package_manager",
        mock_get_package_manager,
    )
    return mock_manager


def test_add_package_manager_not_installed(
    client: TestClient, mock_package_manager_not_installed: Mock
) -> None:
    """Test add_package when package manager is not installed."""
    response = client.post(
        "/api/packages/add",
        headers=HEADERS,
        json={"package": "test-package"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is False
    assert "test-manager is not available" in result["error"]
    mock_package_manager_not_installed.alert_not_installed.assert_called_once()


def test_list_packages_manager_not_installed(
    client: TestClient, mock_package_manager_not_installed: Mock
) -> None:
    """Test list_packages when package manager is not installed."""
    response = client.get(
        "/api/packages/list",
        headers=HEADERS,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["packages"] == []
    mock_package_manager_not_installed.alert_not_installed.assert_called_once()


def test_package_operations_without_session(client: TestClient) -> None:
    """Test package operations without session."""
    headers_no_session = token_header("fake-token")

    endpoints = [
        ("/api/packages/add", "post"),
        ("/api/packages/remove", "post"),
        ("/api/packages/list", "get"),
    ]

    for endpoint, method in endpoints:
        if method == "get":
            response = client.get(endpoint, headers=headers_no_session)
        else:
            response = client.post(
                endpoint,
                headers=headers_no_session,
                json={"package": "test-package"},
            )
        assert response.status_code in [200, 400, 401, 422]


def test_package_operations_with_invalid_authentication(
    client: TestClient,
) -> None:
    """Test package operations with invalid authentication."""
    invalid_headers = {"Marimo-Session-Id": SESSION_ID}  # No token

    endpoints = [
        ("/api/packages/add", "post"),
        ("/api/packages/remove", "post"),
        ("/api/packages/list", "get"),
    ]

    for endpoint, method in endpoints:
        if method == "get":
            response = client.get(endpoint, headers=invalid_headers)
        else:
            response = client.post(
                endpoint,
                headers=invalid_headers,
                json={"package": "test-package"},
            )
        assert response.status_code in [401, 403, 422]


def test_add_package_request_validation(
    client: TestClient, mock_package_manager: Mock
) -> None:
    """Test request validation for add_package endpoint."""
    invalid_requests = [
        {},  # Missing package
        {"package": None},  # Null package
        {"upgrade": True},  # Missing package
    ]

    for invalid_request in invalid_requests:
        with pytest.raises(msgspec.ValidationError):
            client.post(
                "/api/packages/add",
                headers=HEADERS,
                json=invalid_request,
            )
    mock_package_manager.install.assert_not_called()


def test_remove_package_request_validation(
    client: TestClient, mock_package_manager: Mock
) -> None:
    """Test request validation for remove_package endpoint."""
    invalid_requests = [
        {},  # Missing package
        {"package": None},  # Null package
    ]

    for invalid_request in invalid_requests:
        with pytest.raises(msgspec.ValidationError):
            client.post(
                "/api/packages/remove",
                headers=HEADERS,
                json=invalid_request,
            )
    mock_package_manager.uninstall.assert_not_called()


def test_remove_package_manager_not_installed(
    client: TestClient, mock_package_manager_not_installed: Mock
) -> None:
    """Test remove_package when package manager is not installed."""
    response = client.post(
        "/api/packages/remove",
        headers=HEADERS,
        json={"package": "test-package"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is False
    assert "test-manager is not available" in result["error"]
    mock_package_manager_not_installed.alert_not_installed.assert_called_once()


@pytest.fixture
def mock_package_manager_with_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> PackageManager:
    """Mock package manager with dependency tree support."""
    mock_manager = MagicMock(spec=PackageManager)
    mock_manager.is_manager_installed.return_value = True
    from marimo._server.models.packages import DependencyTreeNode

    mock_manager.dependency_tree.return_value = DependencyTreeNode(
        name="root",
        version="1.0.0",
        tags=[],
        dependencies=[
            DependencyTreeNode(
                name="child",
                version="0.1.0",
                tags=[{"kind": "extra", "value": "dev"}],
                dependencies=[],
            )
        ],
    )

    def mock_get_package_manager(request: Any) -> PackageManager:
        del request
        return mock_manager

    monkeypatch.setattr(
        "marimo._server.api.endpoints.packages._get_package_manager",
        mock_get_package_manager,
    )
    return mock_manager


def test_dependency_tree(
    client: TestClient, mock_package_manager_with_tree: Mock
) -> None:
    """Test dependency tree endpoint."""
    response = client.get(
        "/api/packages/tree",
        headers=HEADERS,
    )
    assert response.status_code == 200
    result = response.json()
    assert "tree" in result
    tree = result["tree"]
    assert tree is not None
    assert tree["name"] == "root"
    assert tree["version"] == "1.0.0"
    assert len(tree["dependencies"]) == 1
    assert tree["dependencies"][0]["name"] == "child"
    assert tree["dependencies"][0]["version"] == "0.1.0"
    mock_package_manager_with_tree.dependency_tree.assert_called_once()


def test_dependency_tree_no_tree(
    client: TestClient, mock_package_manager: Mock
) -> None:
    """Test dependency tree endpoint when no tree is available."""
    mock_package_manager.dependency_tree.return_value = None
    response = client.get(
        "/api/packages/tree",
        headers=HEADERS,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["tree"] is None
    mock_package_manager.dependency_tree.assert_called_once()


def test_dependency_tree_without_session(client: TestClient) -> None:
    """Test dependency tree without session."""
    headers_no_session = token_header("fake-token")
    response = client.get(
        "/api/packages/tree",
        headers=headers_no_session,
    )
    assert response.status_code in [200, 400, 401, 422]


@pytest.fixture
def mock_package_manager_with_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> PackageManager:
    """Mock package manager with metadata update functionality."""
    mock_manager = MagicMock(spec=PackageManager)
    mock_manager.install = AsyncMock(return_value=True)
    mock_manager.uninstall = AsyncMock(return_value=True)
    mock_manager.is_manager_installed.return_value = True
    mock_manager.update_notebook_script_metadata = MagicMock()

    def mock_get_package_manager(request: Any) -> PackageManager:
        del request
        return mock_manager

    monkeypatch.setattr(
        "marimo._server.api.endpoints.packages._get_package_manager",
        mock_get_package_manager,
    )
    return mock_manager


def test_add_package_with_metadata_update(
    client: TestClient, mock_package_manager_with_metadata: Mock
) -> None:
    """Test add_package calls metadata update when MANAGE_SCRIPT_METADATA is enabled."""
    with patch(
        "marimo._config.settings.GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA", True
    ):
        with patch(
            "marimo._server.api.endpoints.packages._get_filename",
            return_value="test.py",
        ):
            response = client.post(
                "/api/packages/add",
                headers=HEADERS,
                json={"package": "test-package"},
            )
            assert response.status_code == 200
            result = response.json()
            assert result == {"success": True, "error": None}
            mock_package_manager_with_metadata.update_notebook_script_metadata.assert_called_once()


def test_remove_package_with_metadata_update(
    client: TestClient, mock_package_manager_with_metadata: Mock
) -> None:
    """Test remove_package calls metadata update when MANAGE_SCRIPT_METADATA is enabled."""
    with patch(
        "marimo._config.settings.GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA", True
    ):
        with patch(
            "marimo._server.api.endpoints.packages._get_filename",
            return_value="test.py",
        ):
            response = client.post(
                "/api/packages/remove",
                headers=HEADERS,
                json={"package": "test-package"},
            )
            assert response.status_code == 200
            result = response.json()
            assert result == {"success": True, "error": None}
            mock_package_manager_with_metadata.update_notebook_script_metadata.assert_called_once()


def test_add_package_no_metadata_update_when_disabled(
    client: TestClient, mock_package_manager_with_metadata: Mock
) -> None:
    """Test add_package doesn't call metadata update when MANAGE_SCRIPT_METADATA is disabled."""
    with patch(
        "marimo._config.settings.GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA", False
    ):
        response = client.post(
            "/api/packages/add",
            headers=HEADERS,
            json={"package": "test-package"},
        )
        assert response.status_code == 200
        mock_package_manager_with_metadata.update_notebook_script_metadata.assert_not_called()


def test_add_package_no_metadata_update_when_no_filename(
    client: TestClient, mock_package_manager_with_metadata: Mock
) -> None:
    """Test add_package doesn't call metadata update when no filename is available."""
    with patch(
        "marimo._config.settings.GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA", True
    ):
        with patch(
            "marimo._server.api.endpoints.packages._get_filename",
            return_value=None,
        ):
            response = client.post(
                "/api/packages/add",
                headers=HEADERS,
                json={"package": "test-package"},
            )
            assert response.status_code == 200
            mock_package_manager_with_metadata.update_notebook_script_metadata.assert_not_called()


def test_add_package_with_git_dependency(
    client: TestClient, mock_package_manager_with_metadata: Mock
) -> None:
    """Test add_package with git dependency calls metadata update correctly."""
    with patch(
        "marimo._config.settings.GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA", True
    ):
        with patch(
            "marimo._server.api.endpoints.packages._get_filename",
            return_value="test.py",
        ):
            response = client.post(
                "/api/packages/add",
                headers=HEADERS,
                json={"package": "git+https://github.com/user/repo.git"},
            )
            assert response.status_code == 200
            result = response.json()
            assert result == {"success": True, "error": None}

            # Verify metadata update was called with the git dependency
            mock_package_manager_with_metadata.update_notebook_script_metadata.assert_called_once()
            call_args = mock_package_manager_with_metadata.update_notebook_script_metadata.call_args
            assert call_args.kwargs["filepath"] == "test.py"
            assert (
                "git+https://github.com/user/repo.git"
                in call_args.kwargs["packages_to_add"]
            )


def test_add_package_with_dev_dependency(
    client: TestClient, mock_package_manager: Mock
) -> None:
    """Test add_package with dev dependency calls metadata update correctly."""
    assert isinstance(mock_package_manager, MagicMock)
    response = client.post(
        "/api/packages/add",
        headers=HEADERS,
        json={"package": "test-package", "upgrade": True, "group": "dev"},
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "error": None}
    mock_package_manager.install.assert_called_once_with(
        "test-package", version=None, upgrade=True, group="dev"
    )


def test_remove_package_with_dev_dependency(
    client: TestClient, mock_package_manager: Mock
) -> None:
    """Test remove_package with dev dependency."""
    assert isinstance(mock_package_manager, MagicMock)
    response = client.post(
        "/api/packages/remove",
        headers=HEADERS,
        json={"package": "test-package", "group": "dev"},
    )
    assert response.status_code == 200
    assert response.json() == {"success": True, "error": None}
    mock_package_manager.uninstall.assert_called_once_with(
        "test-package", group="dev"
    )
