# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from marimo._ast.parse import ast_parse

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

LocalModuleKind = Literal["module", "package"]


class LocalWheelError(Exception):
    pass


@dataclass(frozen=True)
class LocalModule:
    name: str
    path: Path
    kind: LocalModuleKind
    root: Path | None = None
    files: tuple[Path, ...] = ()


@dataclass(frozen=True)
class _Import:
    module: str | None
    names: tuple[str, ...]
    level: int


@dataclass(frozen=True)
class _ScanFile:
    path: Path
    package_root: Path | None = None
    package_parts: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Resolved:
    module: LocalModule
    files: tuple[_ScanFile, ...]


def resolve_local_modules(
    notebook: Path,
    roots: Sequence[Path] | None = None,
    exclude_names: Collection[str] | None = None,
) -> tuple[LocalModule, ...]:
    """Return local modules imported by a notebook and its local modules.

    Resolution follows Python's file layout, then keeps scanning resolved local
    files so transitive local imports are included in the export.
    """
    notebook_path = notebook.absolute().resolve()
    import_roots = _import_roots(notebook_path, roots)
    excluded_names = {_canonical_name(name) for name in exclude_names or ()}
    pending = [_ScanFile(notebook_path)]
    scanned: set[Path] = set()
    modules: dict[tuple[str, Path], LocalModule] = {}
    module_files: dict[tuple[str, Path], set[Path]] = {}

    while pending:
        scan = pending.pop()
        path = scan.path.resolve()
        if path in scanned:
            continue
        scanned.add(path)

        for request in _read_imports(path):
            if _is_excluded_import(request, excluded_names):
                continue
            resolved = _resolve_import(request, scan, import_roots)
            if resolved is None:
                continue
            module = resolved.module
            if module.path == notebook_path:
                continue
            key = (module.name, module.path)
            modules.setdefault(key, module)
            module_files.setdefault(key, set()).update(
                file.path.resolve() for file in resolved.files
            )
            pending.extend(
                file for file in resolved.files if file.path not in scanned
            )

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
            key=lambda module: (module.name, module.path),
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


def import_namespaces(path: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                request.module.split(".", 1)[0]
                for request in _read_imports(path)
                if request.level == 0 and request.module is not None
            }
        )
    )


def module_python_files(module: LocalModule) -> tuple[Path, ...]:
    if module.kind == "module":
        return (module.path,)
    if module.files:
        return module.files
    init = module.path / "__init__.py"
    return (init.resolve(),) if init.is_file() else ()


def _canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _is_excluded_import(request: _Import, excluded_names: set[str]) -> bool:
    if not excluded_names or request.level:
        return False
    if request.module is None:
        return any(
            _canonical_name(name) in excluded_names for name in request.names
        )
    return _canonical_name(request.module.split(".", 1)[0]) in excluded_names


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


def _read_imports(path: Path) -> tuple[_Import, ...]:
    try:
        tree = ast_parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        raise LocalWheelError(
            f"Failed to parse local import {path}: {error.msg}"
        ) from error

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.imports: list[_Import] = []

        def visit_Import(self, node: ast.Import) -> None:
            self.imports.extend(
                _Import(alias.name, (), 0) for alias in node.names
            )

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            self.imports.append(
                _Import(
                    node.module,
                    tuple(
                        alias.name for alias in node.names if alias.name != "*"
                    ),
                    node.level,
                )
            )

    visitor = Visitor()
    visitor.visit(tree)
    return tuple(visitor.imports)


def _resolve_import(
    request: _Import, scan: _ScanFile, roots: Sequence[Path]
) -> _Resolved | None:
    if request.level:
        if scan.package_root is None:
            raise LocalWheelError(
                "Notebook relative imports cannot be packaged for html-wasm "
                f"local wheels: {scan.path}"
            )
        parts = _relative_parts(request, scan)
        return _resolve_from_parts(parts, request.names, (scan.package_root,))

    if request.module is None:
        return None
    return _resolve_from_parts(request.module.split("."), request.names, roots)


def _relative_parts(request: _Import, scan: _ScanFile) -> list[str]:
    package_parts = list(scan.package_parts)
    if request.level > 1:
        package_parts = package_parts[: -(request.level - 1)]
    if request.module:
        package_parts.extend(request.module.split("."))
    return package_parts


def _resolve_from_parts(
    parts: list[str], names: Sequence[str], roots: Sequence[Path]
) -> _Resolved | None:
    resolved = _resolve_parts(parts, roots)
    if resolved is not None:
        return _with_from_import_files(resolved, parts, names, roots)

    module: LocalModule | None = None
    files: list[_ScanFile] = []
    for name in names:
        resolved = _resolve_parts([*parts, name], roots)
        if resolved is None:
            continue
        if module is None:
            module = resolved.module
        if resolved.module.path != module.path:
            continue
        files.extend(resolved.files)
    return None if module is None else _Resolved(module, tuple(files))


def _resolve_parts(
    parts: list[str], roots: Sequence[Path]
) -> _Resolved | None:
    if not parts:
        return None

    for root in roots:
        module_file = root / f"{parts[0]}.py"
        if len(parts) == 1 and module_file.is_file():
            module = LocalModule(
                parts[0], module_file.resolve(), "module", root
            )
            return _Resolved(module, (_ScanFile(module.path),))

        package_dir = root / parts[0]
        if not package_dir.is_dir():
            continue
        if len(parts) == 1 and (package_dir / "__init__.py").is_file():
            module = LocalModule(
                parts[0], package_dir.resolve(), "package", root
            )
            return _Resolved(module, _package_scan_files(module, parts))
        if len(parts) > 1:
            files = _package_files_for_parts(root, package_dir, parts)
            if files:
                module = LocalModule(
                    parts[0], package_dir.resolve(), "package", root
                )
                return _Resolved(module, files)

    return None


def _with_from_import_files(
    resolved: _Resolved,
    parts: list[str],
    names: Sequence[str],
    roots: Sequence[Path],
) -> _Resolved:
    if resolved.module.kind != "package":
        return resolved

    files = list(resolved.files)
    seen = {file.path for file in files}
    for name in names:
        child = _resolve_parts([*parts, name], roots)
        if child is None or child.module.path != resolved.module.path:
            continue
        for file in child.files:
            if file.path not in seen:
                seen.add(file.path)
                files.append(file)
    return _Resolved(resolved.module, tuple(files))


def _package_files_for_parts(
    root: Path, package_dir: Path, parts: list[str]
) -> tuple[_ScanFile, ...]:
    files: list[_ScanFile] = []
    package_parts = [parts[0]]
    current = package_dir
    init = current / "__init__.py"
    if init.is_file():
        files.append(_ScanFile(init.resolve(), root, tuple(package_parts)))

    for index, part in enumerate(parts[1:], start=1):
        module_file = current / f"{part}.py"
        if index == len(parts) - 1 and module_file.is_file():
            files.append(
                _ScanFile(module_file.resolve(), root, tuple(package_parts))
            )
            return tuple(files)

        current = current / part
        if not current.is_dir():
            return ()
        package_parts.append(part)
        init = current / "__init__.py"
        if init.is_file():
            files.append(_ScanFile(init.resolve(), root, tuple(package_parts)))

    return tuple(files)


def _package_scan_files(
    module: LocalModule, parts: list[str]
) -> tuple[_ScanFile, ...]:
    init = module.path / "__init__.py"
    if not init.is_file():
        return ()
    root = module.root or module.path.parent
    return (_ScanFile(init.resolve(), root, tuple(parts[:1])),)
