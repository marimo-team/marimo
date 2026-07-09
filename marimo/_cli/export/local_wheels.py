# Copyright 2026 Marimo. All rights reserved.
"""Create hosted wheel dependencies for html-wasm exports.

The export pipeline needs browser-installable requirements. This module turns
two local inputs into that shape:

* PEP 723 local wheel references, such as `pkg @ ./dist/pkg.whl`.
* `LocalModule` values resolved from notebook imports.

Referenced wheels are copied into `public/wheels`. Resolved modules are written
as deterministic pure-Python wheels in a temporary directory. A `module` keeps
the user's single-file layout as top-level `foo.py`. A `package` keeps its
package files under `foo/`. The notebook metadata is then rewritten to
`name @ ../public/wheels/<wheel>.whl` so Pyodide can install the files with
micropip during worker startup.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import re
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote, unquote, urlparse
from urllib.request import url2pathname

from marimo._cli.export.local_modules import (
    LocalModule,
    LocalWheelError,
    module_python_files,
)
from marimo._utils.inline_script_metadata import PyProjectReader
from marimo._utils.scripts import (
    REGEX,
    read_pyproject_from_script,
    write_pyproject_to_script,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from marimo._utils.marimo_path import MarimoPath

WASM_WHEEL_DIR = "public/wheels"
WASM_WHEEL_URL_PREFIX = "../public/wheels"
_DIST_INFO_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_AUTO_WHEEL_VERSION_MARKER = "-0.0.0+marimo."
_DIRECT_REF_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]+\])?)"
    r"\s*@\s*(?P<url>.+?)(?:\s*;\s*(?P<marker>.+))?\s*$"
)
_VALID_METADATA_NAME_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True)
class _WheelDependency:
    name: str
    path: Path
    marker: str | None = None


def copy_local_wheels(
    out_dir: Path,
    wheel_paths: Sequence[Path],
    *,
    source_wheel_dir: Path | None = None,
) -> None:
    wheel_dir = out_dir / WASM_WHEEL_DIR
    current_names = {wheel_path.name for wheel_path in wheel_paths}
    same_as_source = (
        source_wheel_dir is not None
        and wheel_dir.resolve() == source_wheel_dir.resolve()
    )
    if wheel_dir.exists():
        for wheel_path in wheel_dir.glob("*.whl"):
            if wheel_path.name in current_names:
                continue
            if (
                same_as_source
                and _AUTO_WHEEL_VERSION_MARKER not in wheel_path.name
            ):
                continue
            wheel_path.unlink()
    if not wheel_paths:
        return

    wheel_dir.mkdir(parents=True, exist_ok=True)
    for wheel_path in wheel_paths:
        target = wheel_dir / wheel_path.name
        if wheel_path.resolve() != target.resolve():
            shutil.copyfile(wheel_path, target)


def resolve_metadata_wheel_dependencies(
    file_path: MarimoPath,
) -> tuple[_WheelDependency, ...]:
    """Return local wheels referenced by notebook PEP 723 metadata.

    Supported entries are direct wheel references and uv source paths. The
    returned dependency names are later rewritten to hosted wheel URLs.
    """
    if not file_path.is_python():
        return ()
    project = read_pyproject_from_script(
        file_path.path.read_text(encoding="utf-8")
    )
    return (
        ()
        if project is None
        else _metadata_wheel_dependencies_from_project(project, file_path.path)
    )


def wheel_dependency_names(
    dependencies: Sequence[_WheelDependency],
) -> set[str]:
    return {
        _canonical_package_name(dependency.name.split("[", 1)[0])
        for dependency in dependencies
    }


def auto_wheel_dependencies(
    wheel_paths: Sequence[Path],
) -> tuple[_WheelDependency, ...]:
    return tuple(
        _WheelDependency(
            wheel_path.name.split(_AUTO_WHEEL_VERSION_MARKER, 1)[0],
            wheel_path,
        )
        for wheel_path in wheel_paths
    )


def with_wheel_dependencies(
    code: str, wheel_dependencies: Sequence[_WheelDependency]
) -> str:
    """Rewrite notebook PEP 723 dependencies to install hosted wheels."""
    if not wheel_dependencies:
        return code

    project = read_pyproject_from_script(code) or {}
    dependencies = project.get("dependencies")
    if not isinstance(dependencies, list):
        dependencies = []
    dependencies = [str(dependency) for dependency in dependencies]
    replacements = {
        _canonical_package_name(dependency.name.split("[", 1)[0]): dependency
        for dependency in wheel_dependencies
    }
    replaced: set[str] = set()
    rewritten_dependencies: list[str] = []
    for dependency in dependencies:
        package_name = _requirement_package_name(dependency)
        canonical = (
            _canonical_package_name(package_name)
            if package_name is not None
            else None
        )
        if canonical in replacements:
            if canonical not in replaced:
                rewritten_dependencies.append(
                    _wheel_requirement(replacements[canonical])
                )
                replaced.add(canonical)
            continue
        rewritten_dependencies.append(dependency)

    for wheel_dependency in wheel_dependencies:
        dependency = _wheel_requirement(wheel_dependency)
        if dependency not in rewritten_dependencies:
            rewritten_dependencies.append(dependency)
    dependencies = rewritten_dependencies
    project["dependencies"] = dependencies
    _remove_uv_sources(project, set(replacements))

    metadata = write_pyproject_to_script(project)
    if read_pyproject_from_script(code) is None:
        return f"{metadata}\n\n{code}"
    return re.sub(REGEX, metadata, code, count=1)


@contextmanager
def build_local_module_wheels(
    modules: Sequence[LocalModule],
) -> Iterator[tuple[Path, ...]]:
    """Build local module wheels and keep their temp directory alive."""
    if not modules:
        yield ()
        return

    with tempfile.TemporaryDirectory(prefix="marimo-html-wasm-wheels-") as tmp:
        wheel_dir = Path(tmp)
        yield tuple(
            write_pure_python_wheel(module, wheel_dir) for module in modules
        )


def write_pure_python_wheel(
    module: LocalModule,
    wheel_dir: Path,
) -> Path:
    """Write a pure Python wheel preserving the resolved module layout."""
    files = _wheel_files(module)
    content_hash = _content_hash(files)
    metadata_name = _metadata_name(module.name)
    distribution = _wheel_distribution_name(metadata_name)
    version = f"0.0.0+marimo.{content_hash}"
    dist_info = f"{distribution}-{version}.dist-info"
    wheel_path = wheel_dir / f"{distribution}-{version}-py3-none-any.whl"

    payloads = {
        archive_name: path.read_bytes() for archive_name, path in files
    }
    payloads[f"{dist_info}/METADATA"] = _metadata(
        name=metadata_name,
        version=version,
        dependencies=_dependencies(files),
    )
    payloads[f"{dist_info}/WHEEL"] = _wheel_metadata()
    payloads[f"{dist_info}/RECORD"] = _record(payloads, dist_info)

    with zipfile.ZipFile(wheel_path, "w") as wheel:
        for archive_name, data in sorted(payloads.items()):
            info = zipfile.ZipInfo(archive_name, _DIST_INFO_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            wheel.writestr(info, data)

    return wheel_path


def _canonical_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_package_name(dependency: str) -> str | None:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", dependency)
    return match.group(1) if match is not None else None


def _local_wheel_path(url: str, notebook_path: Path) -> Path | None:
    raw_url = url.split("#", 1)[0]
    parsed = urlparse(raw_url)
    if parsed.scheme == "file":
        source_url_path = url2pathname(unquote(parsed.path))
        source_netloc = unquote(parsed.netloc)
        if source_netloc and source_netloc.lower() != "localhost":
            source_url_path = f"//{source_netloc}{source_url_path}"
        source_path = Path(source_url_path)
    elif parsed.scheme:
        return None
    else:
        source_path = Path(raw_url)
    if source_path.suffix != ".whl":
        return None
    if not source_path.is_absolute():
        source_path = notebook_path.parent / source_path
    return source_path.resolve()


def _direct_reference_wheel_dependency(
    dependency: str, notebook_path: Path
) -> _WheelDependency | None:
    match = _DIRECT_REF_RE.match(dependency)
    if match is None:
        return None
    marker = match.group("marker")
    wheel_path = _local_wheel_path(match.group("url"), notebook_path)
    if wheel_path is None:
        return None
    return _WheelDependency(
        match.group("name"),
        wheel_path,
        marker,
    )


def _dependency_metadata(
    dependency: str,
) -> tuple[str, str | None] | None:
    name = _requirement_package_name(dependency)
    if name is None:
        return None
    _, _, marker = dependency.partition(";")
    return name, marker.strip() or None


def _metadata_wheel_dependencies_from_project(
    project: dict[str, object], notebook_path: Path
) -> tuple[_WheelDependency, ...]:
    wheel_dependencies: dict[str, _WheelDependency] = {}
    dependencies = project.get("dependencies")
    dependency_metadata: dict[str, tuple[str, str | None]] = {}
    if isinstance(dependencies, list):
        for dependency in (str(dependency) for dependency in dependencies):
            metadata = _dependency_metadata(dependency)
            if metadata is None:
                continue
            name, _ = metadata
            dependency_metadata[
                _canonical_package_name(name.split("[", 1)[0])
            ] = metadata
            wheel_dependency = _direct_reference_wheel_dependency(
                dependency, notebook_path
            )
            if wheel_dependency is not None:
                canonical = _canonical_package_name(
                    wheel_dependency.name.split("[", 1)[0]
                )
                wheel_dependencies[canonical] = wheel_dependency

    uv_sources = {}
    tool = project.get("tool")
    if isinstance(tool, dict):
        uv = tool.get("uv")
        if isinstance(uv, dict):
            sources = uv.get("sources")
            if isinstance(sources, dict):
                uv_sources = sources
    for source_name, source_config in uv_sources.items():
        if not isinstance(source_config, dict):
            continue
        source_url = source_config.get("path")
        canonical = _canonical_package_name(str(source_name))
        metadata = dependency_metadata.get(canonical)
        if source_url is None or metadata is None:
            continue
        wheel_path = _local_wheel_path(str(source_url), notebook_path)
        if wheel_path is None:
            continue
        name, dependency_marker = metadata
        wheel_dependencies[canonical] = _WheelDependency(
            name,
            wheel_path,
            dependency_marker,
        )

    for wheel_dependency in wheel_dependencies.values():
        if not wheel_dependency.path.is_file():
            raise LocalWheelError(
                f"PEP 723 local wheel dependency does not exist: "
                f"{wheel_dependency.path}"
            )

    return tuple(wheel_dependencies.values())


def _wheel_requirement(dependency: _WheelDependency) -> str:
    url = f"{WASM_WHEEL_URL_PREFIX}/{quote(dependency.path.name)}"
    requirement = f"{dependency.name} @ {url}"
    if dependency.marker is not None:
        requirement += f" ; {dependency.marker}"
    return requirement


def _remove_uv_sources(project: dict[str, object], names: set[str]) -> None:
    tool = project.get("tool")
    if not isinstance(tool, dict):
        return
    uv = tool.get("uv")
    if not isinstance(uv, dict):
        return
    sources = uv.get("sources")
    if not isinstance(sources, dict):
        return
    for source_name in tuple(sources):
        if _canonical_package_name(str(source_name)) in names:
            del sources[source_name]
    if not sources:
        del uv["sources"]
    if not uv:
        del tool["uv"]
    if not tool:
        del project["tool"]


def _wheel_files(module: LocalModule) -> tuple[tuple[str, Path], ...]:
    if module.kind == "module":
        return ((f"{module.name}.py", module.path),)

    return tuple(
        (f"{module.name}/{path.relative_to(module.path).as_posix()}", path)
        for path in module_python_files(module)
    )


def _content_hash(files: Sequence[tuple[str, Path]]) -> str:
    digest = hashlib.sha256()
    for archive_name, path in files:
        digest.update(archive_name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def _dependencies(files: Sequence[tuple[str, Path]]) -> tuple[str, ...]:
    dependencies: set[str] = set()
    for _, path in files:
        project = PyProjectReader.from_script(path.read_text(encoding="utf-8"))
        dependencies.update(
            str(dependency) for dependency in project.dependencies
        )
    return tuple(sorted(dependencies))


def _metadata(
    *, name: str, version: str, dependencies: Sequence[str]
) -> bytes:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
    ]
    lines.extend(f"Requires-Dist: {dependency}" for dependency in dependencies)
    return ("\n".join(lines) + "\n").encode()


def _wheel_metadata() -> bytes:
    return (
        b"Wheel-Version: 1.0\n"
        b"Generator: marimo\n"
        b"Root-Is-Purelib: true\n"
        b"Tag: py3-none-any\n"
    )


def _record(payloads: dict[str, bytes], dist_info: str) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    for archive_name, data in sorted(payloads.items()):
        digest = (
            base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            .rstrip(b"=")
            .decode()
        )
        writer.writerow([archive_name, f"sha256={digest}", str(len(data))])
    writer.writerow([f"{dist_info}/RECORD", "", ""])
    return output.getvalue().encode()


def _wheel_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def _metadata_name(name: str) -> str:
    normalized = re.sub(r"[-_.]+", "-", name).lower()
    if _VALID_METADATA_NAME_RE.match(normalized):
        return normalized
    stem = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "module"
    digest = hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"marimo-local-{stem}-{digest}"
