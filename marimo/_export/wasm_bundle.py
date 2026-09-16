# Copyright 2026 Marimo. All rights reserved.
"""Helpers for self-contained WebAssembly notebook exports."""

from __future__ import annotations

import ast
import hashlib
import html
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from marimo._export.wasm_runtime import resolve_pypi_index_urls
from marimo._pyodide.pyodide_constraints import PYODIDE_VERSION
from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)
from marimo._runtime.packages.utils import (
    filter_requirements_for_emscripten,
    requirement_applies,
    strip_requirement_name,
)
from marimo._utils.inline_script_metadata import PyProjectReader
from marimo._utils.scripts import (
    REGEX,
    read_pyproject_from_script,
    write_pyproject_to_script,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from marimo._utils.marimo_path import MarimoPath


DEFAULT_PYODIDE_INDEX_URL = (
    f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
)


@dataclass(frozen=True)
class WasmBundle:
    pyodide_index_url: str
    pypi_index_urls: tuple[str, ...]


def notebook_wasm_dependencies(path: MarimoPath) -> tuple[str, ...]:
    """Return metadata and statically imported package requirements."""
    code = path.path.read_text(encoding="utf-8")
    requirements: list[str] = []
    try:
        reader = PyProjectReader.from_script(code)
        requirements.extend(
            filter_requirements_for_emscripten(reader.dependencies)
        )
    except Exception:
        pass

    try:
        tree = ast.parse(code, filename=path.absolute_name)
    except SyntaxError:
        tree = None

    mapping = module_name_to_pypi_name()
    imported: set[str] = set()
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])

    stdlib = sys.stdlib_module_names
    for module in sorted(imported):
        if module in stdlib or module in {"marimo", "micropip"}:
            continue
        requirements.append(mapping.get(module, module.replace("_", "-")))

    seen: set[str] = set()
    result: list[str] = []
    for requirement in requirements:
        name = strip_requirement_name(requirement).lower().replace("_", "-")
        if name and name not in seen:
            seen.add(name)
            result.append(requirement)
    return tuple(result)


def build_offline_bundle(
    *,
    path: MarimoPath,
    output_directory: Path,
    pyodide_index_url: str | None,
    pypi_index_urls: Sequence[str],
) -> WasmBundle:
    """Create a standalone bundle using the notebook's Pyodide closure."""
    source_url = pyodide_index_url or DEFAULT_PYODIDE_INDEX_URL
    source_url = _ensure_directory_url(source_url)
    pyodide_directory = output_directory / "pyodide"
    pyodide_directory.mkdir(parents=True, exist_ok=True)

    lockfile = _fetch_bytes(_join_url(source_url, "pyodide-lock.json"))
    lock = _decode_json(lockfile)

    lock_packages = lock.get("packages", {})
    pyodide_packages = {
        _canonical_name(entry.get("name", key)): key
        for key, entry in lock_packages.items()
        if isinstance(entry, dict)
    }
    requirements = [
        "pyodide-http",
        *notebook_wasm_dependencies(path),
        "marimo-base",
    ]
    required_pyodide_packages = {
        pyodide_packages[name]
        for name in (
            "micropip",
            "msgspec",
            "narwhals",
            "packaging",
            "docutils",
            "pygments",
            "jedi",
            "pyodide-http",
            *(
                _canonical_name(strip_requirement_name(req))
                for req in requirements
            ),
        )
        if name in pyodide_packages
    }
    external_requirements = [
        requirement
        for requirement in requirements
        if _canonical_name(strip_requirement_name(requirement))
        not in pyodide_packages
    ]

    wheels_directory = output_directory / "packages" / "wheels"
    wheels_directory.mkdir(parents=True, exist_ok=True)
    required_pyodide_packages.update(
        _download_wheel_closure(
            external_requirements,
            wheels_directory,
            resolve_pypi_index_urls(path, pypi_index_urls),
            python_version=".".join(
                str(lock.get("info", {}).get("python", "3.14")).split(".")[:2]
            ),
            pyodide_packages=pyodide_packages,
        )
    )
    required_pyodide_packages = _pyodide_package_closure(
        required_pyodide_packages, lock_packages
    )
    _copy_pyodide_assets(
        source_url=source_url,
        output_directory=pyodide_directory,
        lockfile=lockfile,
        lock_packages=lock_packages,
        package_keys=required_pyodide_packages,
    )
    _write_simple_index(output_directory / "packages", wheels_directory)

    return WasmBundle(
        pyodide_index_url="./pyodide/",
        pypi_index_urls=("./packages/simple",),
    )


def add_wasm_dependencies(code: str, dependencies: Iterable[str]) -> str:
    """Add inferred dependencies to embedded PEP 723 metadata."""
    additions = list(dependencies)
    if not additions:
        return code
    project = read_pyproject_from_script(code) or {}
    existing = project.get("dependencies")
    existing_values = (
        [str(value) for value in existing]
        if isinstance(existing, list)
        else []
    )
    existing_names = {
        _canonical_name(strip_requirement_name(value))
        for value in existing_values
    }
    for dependency in additions:
        if (
            _canonical_name(strip_requirement_name(dependency))
            not in existing_names
        ):
            existing_values.append(dependency)
    project["dependencies"] = existing_values
    metadata = write_pyproject_to_script(project)
    if read_pyproject_from_script(code) is None:
        return f"{metadata}\n\n{code}"
    return re.sub(REGEX, metadata, code, count=1)


def _pyodide_package_closure(
    package_keys: set[str], packages: dict[str, Any]
) -> set[str]:
    closure = set(package_keys)
    pending = list(package_keys)
    while pending:
        key = pending.pop()
        entry = packages.get(key)
        if not isinstance(entry, dict):
            continue
        for dependency in entry.get("depends", []):
            if dependency in packages and dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    return closure


def _copy_pyodide_assets(
    *,
    source_url: str,
    output_directory: Path,
    lockfile: bytes,
    lock_packages: dict[str, Any],
    package_keys: set[str],
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "pyodide-lock.json").write_bytes(lockfile)
    filenames: set[str] = set()
    for key, entry in lock_packages.items():
        if key not in package_keys or not isinstance(entry, dict):
            continue
        filename = entry.get("file_name")
        if isinstance(filename, str):
            filenames.add(filename)
    filenames.update({"pyodide.asm.wasm", "python_stdlib.zip"})
    optional = {
        "pyodide.js",
        "pyodide.mjs",
        "pyodide.asm.js",
        "pyodide.asm.mjs",
    }
    for filename in sorted(filenames | optional):
        try:
            contents = _fetch_bytes(_join_url(source_url, filename))
        except (FileNotFoundError, urllib.error.HTTPError) as error:
            if filename in optional and (
                isinstance(error, FileNotFoundError) or error.code == 404
            ):
                continue
            raise
        (output_directory / filename).write_bytes(contents)


def _download_wheel_closure(
    requirements: Sequence[str],
    destination: Path,
    index_urls: Sequence[str],
    python_version: str,
    pyodide_packages: dict[str, str],
) -> set[str]:
    from packaging.markers import default_environment
    from packaging.requirements import Requirement

    pending = list(requirements)
    processed: set[str] = set()
    required_pyodide_packages: set[str] = set()
    environment = {
        str(key): str(value) for key, value in default_environment().items()
    }
    environment["sys_platform"] = "emscripten"

    while pending:
        requirement_text = pending.pop(0)
        requirement = Requirement(requirement_text)
        name = _canonical_name(requirement.name)
        if name in processed or not requirement_applies(
            requirement_text, marker_environment=environment
        ):
            continue
        if name in pyodide_packages:
            required_pyodide_packages.add(pyodide_packages[name])
            continue
        processed.add(name)

        before = set(destination.glob("*.whl"))
        pip_executable = shutil.which("pip")
        uvx_executable = shutil.which("uvx")
        command = (
            [pip_executable]
            if pip_executable
            else (
                [uvx_executable, "--from", "pip", "pip"]
                if uvx_executable
                else [sys.executable, "-m", "pip"]
            )
        ) + ["download"]
        if index_urls:
            command.extend(["--index-url", index_urls[0]])
            for extra in index_urls[1:]:
                command.extend(["--extra-index-url", extra])
        command.extend(
            [
                "--disable-pip-version-check",
                "--no-deps",
                "--only-binary=:all:",
                "--platform",
                "any",
                "--implementation",
                "py",
                "--abi",
                "none",
                "--python-version",
                python_version,
                "--dest",
                str(destination),
                requirement_text,
            ]
        )
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            raise RuntimeError(
                f"Could not resolve WASM package {requirement_text}: {detail}"
            ) from error

        wheels = sorted(set(destination.glob("*.whl")) - before)
        if not wheels:
            wheels = sorted(
                wheel
                for wheel in destination.glob("*.whl")
                if _canonical_name(wheel.name.split("-", 1)[0]) == name
            )
        if not wheels:
            raise RuntimeError(f"No wheel downloaded for {requirement_text}")
        for wheel in wheels:
            pending.extend(_wheel_requirements(wheel, environment))
    return required_pyodide_packages


def _wheel_requirements(wheel: Path, environment: dict[str, str]) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        )
        metadata = Parser().parsestr(
            archive.read(metadata_name).decode("utf-8")
        )
    return [
        value
        for value in metadata.get_all("Requires-Dist", [])
        if requirement_applies(value, marker_environment=environment)
    ]


def _write_simple_index(
    packages_directory: Path, wheels_directory: Path
) -> None:
    simple_directory = packages_directory / "simple"
    simple_directory.mkdir(parents=True, exist_ok=True)
    package_links: dict[str, list[tuple[str, str]]] = {}
    for wheel in sorted(wheels_directory.glob("*.whl")):
        with zipfile.ZipFile(wheel) as archive:
            metadata_name = next(
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            )
            name = (
                Parser()
                .parsestr(archive.read(metadata_name).decode("utf-8"))
                .get("Name")
            )
        if not name:
            continue
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        canonical = _canonical_name(name)
        package_links.setdefault(canonical, []).append((wheel.name, digest))

    top_links = []
    for package, links in sorted(package_links.items()):
        package_directory = simple_directory / package
        package_directory.mkdir(parents=True, exist_ok=True)
        anchors = "\n".join(
            f'<a href="../../wheels/{urllib.parse.quote(filename)}#sha256={digest}">{html.escape(filename)}</a>'
            for filename, digest in links
        )
        (package_directory / "index.html").write_text(
            f"<html><body>{anchors}</body></html>\n", encoding="utf-8"
        )
        top_links.append(f'<a href="{package}/">{package}</a>')
    (simple_directory / "index.html").write_text(
        f"<html><body>{' '.join(top_links)}</body></html>\n",
        encoding="utf-8",
    )


def _fetch_bytes(url: str) -> bytes:
    local_path = _local_path(url)
    if local_path is not None:
        return local_path.read_bytes()
    with urllib.request.urlopen(url, timeout=60) as response:
        return cast(bytes, response.read())


def _join_url(base: str, name: str) -> str:
    local_path = _local_path(base)
    if local_path is not None:
        return str(local_path / name)
    return urllib.parse.urljoin(base, name)


def _ensure_directory_url(value: str) -> str:
    return value if value.endswith(("/", "\\")) else f"{value}/"


def _local_path(value: str) -> Path | None:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme in ("http", "https"):
        return None
    if parsed.scheme == "file":
        return Path(urllib.request.url2pathname(parsed.path))
    return Path(value)


def _decode_json(contents: bytes) -> dict[str, Any]:
    import json

    value = json.loads(contents)
    if not isinstance(value, dict):
        raise ValueError("Pyodide lockfile must contain an object")
    return value


def _canonical_name(value: str) -> str:
    return value.replace("_", "-").replace(".", "-").lower()
