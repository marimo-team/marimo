# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.commands import (
    ListPackagesCommand,
    PackagesDependencyTreeCommand,
    kebab_case,
)
from marimo._types.ids import RequestId


def test_kebab_case() -> None:
    assert kebab_case("SomeSQLCommand") == "some-sql"
    assert kebab_case("SomeSQL") == "some-sql"
    assert kebab_case("MyNotificationCommand") == "my-notification"


def test_packages_commands_kebab_case() -> None:
    assert kebab_case("ListPackagesCommand") == "list-packages"
    assert (
        kebab_case("PackagesDependencyTreeCommand")
        == "packages-dependency-tree"
    )


def test_list_packages_command() -> None:
    request_id = RequestId("test-request-id")
    cmd = ListPackagesCommand(request_id=request_id)
    assert cmd.request_id == request_id


def test_packages_dependency_tree_command() -> None:
    request_id = RequestId("test-request-id")
    cmd = PackagesDependencyTreeCommand(request_id=request_id)
    assert cmd.request_id == request_id
    assert cmd.filename is None

    cmd_with_filename = PackagesDependencyTreeCommand(
        request_id=request_id, filename="/path/to/notebook.py"
    )
    assert cmd_with_filename.filename == "/path/to/notebook.py"
