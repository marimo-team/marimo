from __future__ import annotations

import pytest

from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.pypi_package_manager import (
    PY_EXE,
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
        "nb.py",
        packages_to_add=["foo"],
        packages_to_remove=["bar"],
        upgrade=False,
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
    pm.update_notebook_script_metadata(
        "nb.py", packages_to_add=["baz"], upgrade=False
    )
    assert runs_calls == []

    # It will attempt to uninstall even if not in the version map
    pm.update_notebook_script_metadata(
        "nb.py", packages_to_remove=["baz"], upgrade=False
    )
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
    pm.update_notebook_script_metadata(
        "nb.py", packages_to_add=["ibis"], upgrade=False
    )
    assert runs_calls == [
        ["uv", "--quiet", "add", "--script", "nb.py", "ibis==2.0"],
    ]
    runs_calls.clear()

    # It should not canonicalize when passed as an import name
    # case-insensitive
    pm.update_notebook_script_metadata(
        "nb.py", import_namespaces_to_add=["yaml"], upgrade=False
    )
    assert runs_calls == [
        ["uv", "--quiet", "add", "--script", "nb.py", "PyYAML==1.0"],
    ]
    runs_calls.clear()

    # It should not canonicalize when passed as an import name
    # and works with brackets
    pm.update_notebook_script_metadata(
        "nb.py", import_namespaces_to_add=["ibis"], upgrade=False
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


def test_update_script_metadata_marimo_packages() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(self, command: list[str]) -> bool:
            runs_calls.append(command)
            return True

        def _get_version_map(self) -> dict[str, str]:
            return {
                "marimo": "0.1.0",
                "marimo-ai": "0.2.0",
                "pandas": "2.0.0",
            }

    pm = MockUvPackageManager()

    # Test 1: Basic package handling
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=[
            "marimo-ai",  # Should have version (different package)
            "pandas",  # Should have version
        ],
        upgrade=False,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "marimo-ai==0.2.0",
            "pandas==2.0.0",
        ]
    ]
    runs_calls.clear()

    # Test 2: Marimo package consolidation - should prefer marimo[ai] over marimo
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=[
            "marimo",
            "marimo[sql]",
            "pandas",
        ],
        upgrade=False,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "marimo",
            "marimo[sql]",
            "pandas==2.0.0",
        ]
    ]
    runs_calls.clear()

    # Test 3: Multiple marimo extras - should use first one
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=[
            "marimo",
            "marimo[sql]",
            "marimo[recommended]",
            "pandas",
        ],
        upgrade=False,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "marimo",
            "marimo[sql]",
            "marimo[recommended]",
            "pandas==2.0.0",
        ]
    ]
    runs_calls.clear()

    # Test 4: Only plain marimo
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=[
            "marimo",
            "pandas",
        ],
        upgrade=False,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "marimo",
            "pandas==2.0.0",
        ]
    ]
    runs_calls.clear()

    # Test 5: Upgrade
    pm.update_notebook_script_metadata(
        filepath="nb.py",
        packages_to_add=["pandas"],
        upgrade=True,
    )
    assert runs_calls == [
        [
            "uv",
            "--quiet",
            "add",
            "--script",
            "nb.py",
            "--upgrade",
            "pandas==2.0.0",
        ],
    ]
    runs_calls.clear()


async def test_uv_pip_install() -> None:
    runs_calls: list[list[str]] = []

    class MockUvPackageManager(UvPackageManager):
        def run(self, command: list[str]) -> bool:
            runs_calls.append(command)
            return True

    pm = MockUvPackageManager()
    await pm._install("foo", upgrade=False)
    assert runs_calls == [
        ["uv", "pip", "install", "--compile", "foo", "-p", PY_EXE],
    ]
