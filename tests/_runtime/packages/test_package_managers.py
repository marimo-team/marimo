from __future__ import annotations

import pytest

from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.pypi_package_manager import (
    MicropipPackageManager,
    PipPackageManager,
    RyePackageManager,
    UvPackageManager,
)


def test_create_package_managers() -> None:
    assert isinstance(create_package_manager("pip"), PipPackageManager)
    assert isinstance(
        create_package_manager("micropip"), MicropipPackageManager
    )
    assert isinstance(create_package_manager("rye"), RyePackageManager)
    assert isinstance(create_package_manager("uv"), UvPackageManager)

    with pytest.raises(RuntimeError) as e:
        create_package_manager("foobar")
    assert "Unknown package manager" in str(e)


def test_update_script_metadata() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(self, command: list[str]) -> bool:
            runs_calls.append(command)
            return True

        def _get_version_map(self) -> dict[str, str]:
            return {"foo": "1.0", "bar": "2.0"}

    pm = MockUvPackageManager()
    pm.update_notebook_script_metadata(
        "nb.py", packages_to_add=["foo"], packages_to_remove=["bar"]
    )
    assert runs_calls == [
        ["uv", "--quiet", "add", "--script", "nb.py", "foo==1.0"],
        ["uv", "--quiet", "remove", "--script", "nb.py", "bar"],
    ]

    runs_calls.clear()


def test_update_script_metadata_with_version_map() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(self, command: list[str]) -> bool:
            runs_calls.append(command)
            return True

        def _get_version_map(self) -> dict[str, str]:
            return {"foo": "1.0", "bar": "2.0"}

    pm = MockUvPackageManager()
    # It should ignore when not in the version map
    # as this implies it failed to install
    pm.update_notebook_script_metadata("nb.py", packages_to_add=["baz"])
    assert runs_calls == []

    # It will attempt to uninstall even if not in the version map
    pm.update_notebook_script_metadata("nb.py", packages_to_remove=["baz"])
    assert runs_calls == [
        ["uv", "--quiet", "remove", "--script", "nb.py", "baz"],
    ]


def test_update_script_metadata_with_mapping() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(self, command: list[str]) -> bool:
            runs_calls.append(command)
            return True

        def _get_version_map(self) -> dict[str, str]:
            return {"ibis": "2.0", "ibis-framework": "2.0", "pyyaml": "1.0"}

    pm = MockUvPackageManager()
    # It should not canonicalize when passed explicitly
    pm.update_notebook_script_metadata("nb.py", packages_to_add=["ibis"])
    assert runs_calls == [
        ["uv", "--quiet", "add", "--script", "nb.py", "ibis==2.0"],
    ]
    runs_calls.clear()

    # It should not canonicalize when passed as an import name
    # case-insensitive
    pm.update_notebook_script_metadata(
        "nb.py", import_namespaces_to_add=["yaml"]
    )
    assert runs_calls == [
        ["uv", "--quiet", "add", "--script", "nb.py", "PyYAML==1.0"],
    ]
    runs_calls.clear()

    # It should not canonicalize when passed as an import name
    # and works with brackets
    pm.update_notebook_script_metadata(
        "nb.py", import_namespaces_to_add=["ibis"]
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "ibis-framework[duckdb]==2.0",
        ],
    ]
