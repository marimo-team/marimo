# Copyright 2026 Marimo. All rights reserved.
"""Resolve notebook-local Python imports from Ruff's import graph.

Ruff reports file-to-file dependencies for the notebook directory plus
configured import roots. marimo keeps the html-wasm specific step: filter those
dependencies to local Python files and group them into wheel-shaped modules:

    import foo          -> foo.py or foo/__init__.py
    from foo import bar -> foo.py or package files under foo/

If notebook.py imports foo.py and foo.py imports bar.py from the same root, the
Ruff graph links both files and both are returned for export.

`LocalModuleKind` records the source layout the wheel builder must preserve. A
`module` is a single-file import such as `foo.py`, which becomes top-level
`foo.py` in the wheel. A `package` is a directory-backed import such as
`foo/__init__.py` or `foo/bar.py`, which keeps files under `foo/` in the wheel.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from marimo._cli.errors import MarimoCLIMissingDependencyError
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.uv import find_uv_bin

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

LocalModuleKind = Literal["module", "package"]
_RUFF_REQUIREMENT = "ruff==0.15.18"
_RUFF_GRAPH_TIMEOUT_SECONDS = 120


class LocalWheelError(Exception):
    pass


@dataclass(frozen=True)
class LocalModule:
    name: str
    path: Path
    kind: LocalModuleKind
    root: Path | None = None
    files: tuple[Path, ...] = ()


def resolve_local_modules(
    notebook: Path,
    roots: Sequence[Path] | None = None,
    exclude_names: Collection[str] | None = None,
) -> tuple[LocalModule, ...]:
    """Return local modules reached from the notebook's imports.

    For example, if notebook.py imports foo.py and foo.py imports bar.py from
    the same import root, this returns entries for both foo.py and bar.py so
    both files can be packaged into the html-wasm export.
    """
    notebook_path = notebook.absolute().resolve()
    import_roots = _import_roots(notebook_path, roots)
    excluded_names = {_canonical_name(name) for name in exclude_names or ()}
    graph = _ruff_import_graph(
        (notebook_path, *import_roots), import_roots, notebook_path
    )
    pending = [notebook_path]
    scanned: set[Path] = set()
    modules: dict[tuple[str, Path], LocalModule] = {}
    module_files: dict[tuple[str, Path], set[Path]] = {}

    while pending:
        path = pending.pop().resolve()
        if path in scanned:
            continue
        scanned.add(path)

        for dependency in graph.get(path, ()):
            module = _local_module_from_path(dependency, import_roots)
            if module is None:
                continue
            if (
                module.path == notebook_path
                or _canonical_name(module.name) in excluded_names
            ):
                continue
            key = (module.name, module.path)
            modules.setdefault(key, module)
            module_files.setdefault(key, set()).update(
                _module_files_for_dependency(module, dependency)
            )
            if dependency not in scanned:
                pending.append(dependency)

    return tuple(
        sorted(
            (
                LocalModule(
                    module.name,
                    module.path,
                    module.kind,
                    module.root,
                    tuple(sorted(module_files.get(key, ()))),
                )
                for key, module in modules.items()
            ),
            key=attrgetter("name", "path"),
        )
    )


def resolve_notebook_local_modules(
    name: str, *, exclude_names: Collection[str] | None = None
) -> tuple[LocalModule, ...]:
    """Resolve local modules with the notebook's configured import roots."""
    from marimo._config.manager import get_default_config_manager
    from marimo._utils.marimo_path import MarimoPath

    marimo_path = MarimoPath(name)
    if not marimo_path.is_python():
        return ()

    config = get_default_config_manager(
        current_path=marimo_path.absolute_name
    ).get_config()
    pythonpath = config["runtime"].get("pythonpath") or []
    roots = tuple(reversed([Path(path) for path in pythonpath]))
    return resolve_local_modules(
        marimo_path.path, roots=roots, exclude_names=exclude_names
    )


def module_python_files(module: LocalModule) -> tuple[Path, ...]:
    """Return the Python files that should be written into a local wheel."""
    if module.kind == "module":
        return (module.path,)
    if module.files:
        return module.files
    init = module.path / "__init__.py"
    return (init.resolve(),) if init.is_file() else ()


def _canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _import_roots(
    notebook: Path, roots: Sequence[Path] | None
) -> tuple[Path, ...]:
    import_roots: list[Path] = []
    seen: set[Path] = set()
    for root in (notebook.parent, *(roots or ())):
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        import_roots.append(resolved)
    return tuple(import_roots)


def _ruff_import_graph(
    files: Sequence[Path], roots: Sequence[Path], notebook: Path
) -> Mapping[Path, tuple[Path, ...]]:
    """Return Ruff's direct import graph for the files being scanned."""
    if not files:
        return {}

    command = _ruff_graph_command(files, roots)
    try:
        result = subprocess.run(
            command,
            cwd=notebook.parent,
            capture_output=True,
            text=True,
            timeout=_RUFF_GRAPH_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LocalWheelError(
            "Failed to run uv while resolving local imports for "
            "html-wasm export."
        ) from error

    if result.returncode != 0 or result.stderr.strip():
        detail = result.stderr.strip() or result.stdout.strip()
        raise LocalWheelError(
            "Failed to analyze local imports with Ruff"
            + (f": {detail}" if detail else ".")
        )

    try:
        raw_graph = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise LocalWheelError(
            "Ruff returned invalid import graph output."
        ) from error
    if not isinstance(raw_graph, dict):
        raise LocalWheelError("Ruff returned invalid import graph output.")

    graph: dict[Path, tuple[Path, ...]] = {}
    for source, dependencies in raw_graph.items():
        if not isinstance(source, str) or not isinstance(dependencies, list):
            raise LocalWheelError("Ruff returned invalid import graph output.")
        graph[_graph_path(source, notebook)] = tuple(
            _graph_path(dependency, notebook)
            for dependency in dependencies
            if isinstance(dependency, str)
        )
    return graph


def _ruff_graph_command(
    files: Sequence[Path], roots: Sequence[Path]
) -> tuple[str, ...]:
    return (
        _uv_bin(),
        "--quiet",
        "--no-progress",
        "tool",
        "run",
        "--from",
        _RUFF_REQUIREMENT,
        "--python",
        sys.executable,
        "--no-python-downloads",
        "ruff",
        "analyze",
        "graph",
        "--preview",
        "--isolated",
        "--config",
        _ruff_src_config(roots),
        *(str(path) for path in files),
    )


def _uv_bin() -> str:
    uv_bin = find_uv_bin()
    if uv_bin == "uv" and not DependencyManager.which("uv"):
        raise MarimoCLIMissingDependencyError(
            "uv must be installed to resolve local imports for "
            "html-wasm export.",
            "uv",
            additional_tip="Install uv from https://github.com/astral-sh/uv",
        )
    return uv_bin


def _ruff_src_config(roots: Sequence[Path]) -> str:
    return "src = [" + ", ".join(json.dumps(str(root)) for root in roots) + "]"


def _graph_path(path: str, notebook: Path) -> Path:
    graph_path = Path(path)
    if not graph_path.is_absolute():
        graph_path = notebook.parent / graph_path
    return graph_path.resolve()


def _local_module_from_path(
    path: Path, roots: Sequence[Path]
) -> LocalModule | None:
    if path.suffix != ".py":
        return None
    path = path.resolve()
    for root in roots:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if not relative.parts:
            continue
        if len(relative.parts) == 1:
            return LocalModule(relative.stem, path, "module", root)
        package_dir = (root / relative.parts[0]).resolve()
        if package_dir.is_dir():
            return LocalModule(relative.parts[0], package_dir, "package", root)
    return None


def _module_files_for_dependency(
    module: LocalModule, dependency: Path
) -> tuple[Path, ...]:
    if module.kind == "module":
        return (module.path,)

    files: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            files.append(resolved)

    current = module.path
    init = current / "__init__.py"
    if init.is_file():
        add(init)
    try:
        relative = dependency.resolve().relative_to(module.path)
    except ValueError:
        return tuple(files)
    for part in relative.parts[:-1]:
        current = current / part
        init = current / "__init__.py"
        if init.is_file():
            add(init)
    if dependency.is_file():
        add(dependency)
    return tuple(files)
