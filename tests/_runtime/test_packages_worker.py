# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._messaging.notification import (
    ListPackagesResultNotification,
    PackagesDependencyTreeResultNotification,
)
from marimo._runtime.commands import (
    ListPackagesCommand,
    PackagesDependencyTreeCommand,
)
from marimo._runtime.packages.utils import PackageDescription
from marimo._runtime.packages_worker import (
    _handle_dependency_tree,
    _handle_list_packages,
)
from marimo._types.ids import RequestId
from marimo._utils.uv_tree import DependencyTreeNode
from tests._messaging.mocks import MockStream


def test_handle_list_packages() -> None:
    """Test _handle_list_packages handler."""
    stream = MockStream()

    packages = [
        PackageDescription(name="numpy", version="1.24.0"),
        PackageDescription(name="pandas", version="2.0.0"),
    ]

    callbacks = MagicMock()
    callbacks.list_packages.return_value = packages

    request = ListPackagesCommand(request_id=RequestId("test-request-id"))

    _handle_list_packages(request, callbacks, stream)

    callbacks.list_packages.assert_called_once()

    assert len(stream.messages) == 1
    notification = stream.parsed_operations[0]
    assert isinstance(notification, ListPackagesResultNotification)
    assert notification.request_id == "test-request-id"
    assert len(notification.packages) == 2


def test_handle_list_packages_exception() -> None:
    """Test _handle_list_packages handles exceptions gracefully."""
    stream = MockStream()

    callbacks = MagicMock()
    callbacks.list_packages.side_effect = Exception("Test error")

    request = ListPackagesCommand(request_id=RequestId("test-request-id"))

    _handle_list_packages(request, callbacks, stream)

    assert len(stream.messages) == 1
    notification = stream.parsed_operations[0]
    assert isinstance(notification, ListPackagesResultNotification)
    assert notification.request_id == "test-request-id"
    assert notification.packages == []


def test_handle_dependency_tree() -> None:
    """Test _handle_dependency_tree handler."""
    stream = MockStream()

    tree = DependencyTreeNode(
        name="marimo",
        version="0.10.0",
        tags=[],
        dependencies=[
            DependencyTreeNode(
                name="starlette",
                version="0.37.0",
                tags=[],
                dependencies=[],
            )
        ],
    )

    callbacks = MagicMock()
    callbacks.dependency_tree.return_value = tree

    request = PackagesDependencyTreeCommand(
        request_id=RequestId("test-request-id"),
        filename="/path/to/notebook.py",
    )

    _handle_dependency_tree(request, callbacks, stream)

    callbacks.dependency_tree.assert_called_once_with("/path/to/notebook.py")

    assert len(stream.messages) == 1
    notification = stream.parsed_operations[0]
    assert isinstance(notification, PackagesDependencyTreeResultNotification)
    assert notification.request_id == "test-request-id"
    assert notification.tree is not None
    assert notification.tree.name == "marimo"


def test_handle_dependency_tree_none_filename() -> None:
    """Test _handle_dependency_tree with None filename."""
    stream = MockStream()

    tree = DependencyTreeNode(
        name="<root>",
        version=None,
        tags=[],
        dependencies=[],
    )

    callbacks = MagicMock()
    callbacks.dependency_tree.return_value = tree

    request = PackagesDependencyTreeCommand(
        request_id=RequestId("test-request-id"),
        filename=None,
    )

    _handle_dependency_tree(request, callbacks, stream)

    callbacks.dependency_tree.assert_called_once_with(None)


def test_handle_dependency_tree_exception() -> None:
    """Test _handle_dependency_tree handles exceptions gracefully."""
    stream = MockStream()

    callbacks = MagicMock()
    callbacks.dependency_tree.side_effect = Exception("Test error")

    request = PackagesDependencyTreeCommand(
        request_id=RequestId("test-request-id"),
        filename=None,
    )

    _handle_dependency_tree(request, callbacks, stream)

    assert len(stream.messages) == 1
    notification = stream.parsed_operations[0]
    assert isinstance(notification, PackagesDependencyTreeResultNotification)
    assert notification.request_id == "test-request-id"
    assert notification.tree is None
