from __future__ import annotations

import json
from typing import TYPE_CHECKING
from urllib.error import HTTPError

from marimo._export.wasm_bundle import (
    _pyodide_package_closure,
    add_wasm_dependencies,
    build_offline_bundle,
    notebook_wasm_dependencies,
)
from marimo._export.wasm_runtime import public_pypi_index_urls
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from pathlib import Path


def test_public_index_urls_remove_credentials() -> None:
    assert public_pypi_index_urls(
        [
            "https://user:secret@example.test/simple/",
            "https://mirror.test/simple/",
        ]
    ) == (
        "https://example.test/simple/",
        "https://mirror.test/simple/",
    )


def test_notebook_wasm_dependencies_include_metadata_and_imports(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text(
        """# /// script
# dependencies = ["requests==2.32.0"]
# ///
import yaml
import requests
""",
        encoding="utf-8",
    )

    dependencies = notebook_wasm_dependencies(MarimoPath(str(notebook)))

    assert dependencies == ("requests==2.32.0", "PyYAML")


def test_add_wasm_dependencies_creates_metadata() -> None:
    code = "import requests\n"

    transformed = add_wasm_dependencies(code, ["requests", "pyyaml"])

    assert 'dependencies = ["requests", "pyyaml"]' in transformed
    assert transformed.endswith(code)


def test_pyodide_package_closure_follows_lock_dependencies() -> None:
    packages = {
        "root": {"depends": ["dependency"]},
        "dependency": {"depends": ["leaf"]},
        "leaf": {"depends": []},
        "unused": {"depends": []},
    }

    assert _pyodide_package_closure({"root"}, packages) == {
        "root",
        "dependency",
        "leaf",
    }


def test_offline_bundle_uses_standard_lockfile_and_relative_urls(
    monkeypatch, tmp_path: Path
) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text("import requests\n", encoding="utf-8")
    lock = {
        "info": {"python": "3.14.0"},
        "packages": {
            "msgspec": {
                "name": "msgspec",
                "file_name": "msgspec-1.0-py3-none-any.whl",
                "package_type": "package",
            }
        },
    }

    def fetch(url: str) -> bytes:
        if url.endswith("pyodide-lock.json"):
            return json.dumps(lock).encode()
        if url.endswith(("pyodide.asm.wasm", "python_stdlib.zip")):
            return b"asset"
        if url.endswith("msgspec-1.0-py3-none-any.whl"):
            return b"wheel"
        raise HTTPError(url, 404, "not found", {}, None)

    monkeypatch.setattr("marimo._export.wasm_bundle._fetch_bytes", fetch)

    def no_download(*_args: object, **_kwargs: object) -> set[str]:
        return set()

    monkeypatch.setattr(
        "marimo._export.wasm_bundle._download_wheel_closure",
        no_download,
    )

    result = build_offline_bundle(
        path=MarimoPath(str(notebook)),
        output_directory=tmp_path / "dist",
        pyodide_index_url="https://pyodide.example/full/",
        pypi_index_urls=("https://pypi.example/simple/",),
    )

    assert result.pyodide_index_url == "./pyodide/"
    assert result.pypi_index_urls == ("./packages/simple",)
    assert (tmp_path / "dist/pyodide/pyodide-lock.json").exists()
    assert (tmp_path / "dist/pyodide/msgspec-1.0-py3-none-any.whl").exists()
    assert (tmp_path / "dist/pyodide/python_stdlib.zip").exists()
    assert (tmp_path / "dist/packages/simple/index.html").exists()
