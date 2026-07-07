# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import base64
import csv
import hashlib
import io
import re
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from marimo._ast.parse import ast_parse
from marimo._utils.inline_script_metadata import PyProjectReader

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Sequence

LocalModuleKind = Literal["module", "package"]

_DIST_INFO_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


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
class _ImportRequest:
    module: str | None
    names: tuple[str, ...]
    level: int


@dataclass(frozen=True)
class _ScanPath:
    path: Path
    package_root: Path | None = None
    package_parts: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ResolvedImport:
    module: LocalModule
    scan_paths: tuple[_ScanPath, ...]


def resolve_local_modules(
    notebook: Path,
    roots: Sequence[Path] | None = None,
    excluded_distributions: Collection[str] = (),
) -> tuple[LocalModule, ...]:
    notebook_path = notebook.absolute()
    resolved_notebook = notebook_path.resolve()
    import_roots = _import_roots(notebook_path, roots)
    excluded = frozenset(excluded_distributions)
    pending = [_ScanPath(notebook_path)]
    scanned: set[tuple[Path, Path | None, tuple[str, ...]]] = set()
    modules: dict[tuple[str, Path], LocalModule] = {}
    module_files: dict[tuple[str, Path], set[Path]] = {}

    while pending:
        scan_path = pending.pop()
        scan_key = _scan_key(scan_path)
        if scan_key in scanned:
            continue
        scanned.add(scan_key)

        for request in _read_imports(scan_path.path):
            for resolved in _resolve_import(
                request,
                scan_path.path,
                import_roots,
                excluded,
                (scan_path.package_root, scan_path.package_parts)
                if scan_path.package_root is not None
                else None,
            ):
                module = resolved.module
                if module.path == resolved_notebook:
                    continue
                key = (module.name, module.path)
                modules.setdefault(key, module)
                module_files.setdefault(key, set()).update(
                    _scan_files_for_module(module, resolved.scan_paths)
                )
                pending.extend(
                    scan_path
                    for scan_path in resolved.scan_paths
                    if _scan_key(scan_path) not in scanned
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


def _import_roots(
    notebook: Path, roots: Sequence[Path] | None
) -> tuple[Path, ...]:
    candidates = (notebook.parent, *(roots or ()))
    seen: set[Path] = set()
    import_roots: list[Path] = []
    for root in candidates:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        import_roots.append(resolved)
    return tuple(import_roots)


@contextmanager
def build_local_module_wheels(
    modules: Sequence[LocalModule],
) -> Iterator[tuple[Path, ...]]:
    if not modules:
        yield ()
        return

    with tempfile.TemporaryDirectory(prefix="marimo-html-wasm-wheels-") as tmp:
        wheel_dir = Path(tmp)
        yield tuple(
            write_pure_python_wheel(module, wheel_dir) for module in modules
        )


def local_module_files(modules: Sequence[LocalModule]) -> tuple[Path, ...]:
    return tuple(
        file for module in modules for file in _module_python_files(module)
    )


def write_pure_python_wheel(module: LocalModule, wheel_dir: Path) -> Path:
    files = _wheel_files(module)
    content_hash = _content_hash(files)
    distribution = _wheel_distribution_name(module.name)
    metadata_name = _metadata_name(module.name)
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


def _read_imports(path: Path) -> tuple[_ImportRequest, ...]:
    try:
        contents = path.read_text(encoding="utf-8")
        tree = ast_parse(contents, filename=str(path))
    except SyntaxError as error:
        message = f"Failed to parse local import {path}: {error.msg}"
        raise LocalWheelError(message) from error

    class ImportVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.requests: list[_ImportRequest] = []

        def visit_If(self, node: ast.If) -> None:
            if _is_type_checking_test(node.test):
                for statement in node.orelse:
                    self.visit(statement)
                return
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            self.requests.extend(
                _ImportRequest(alias.name, (), 0) for alias in node.names
            )

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            self.requests.append(
                _ImportRequest(
                    node.module,
                    tuple(
                        alias.name for alias in node.names if alias.name != "*"
                    ),
                    node.level,
                )
            )

    visitor = ImportVisitor()
    visitor.visit(tree)
    return tuple(visitor.requests)


def _is_type_checking_test(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "TYPE_CHECKING"
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
    )


def _resolve_import(
    request: _ImportRequest,
    importer: Path,
    roots: Sequence[Path],
    excluded_distributions: frozenset[str],
    package_context: tuple[Path, Sequence[str]] | None = None,
) -> tuple[_ResolvedImport, ...]:
    if request.level == 0:
        if request.module is None:
            return ()
        parts = request.module.split(".")
        if _metadata_name(parts[0]) in excluded_distributions:
            return ()
        module = _resolve_module(
            parts, roots, allow_bare_namespace=bool(request.names)
        )
        if module is None:
            resolved_imports = [
                _resolved_import(
                    [*parts, name], _resolve_module([*parts, name], roots)
                )
                for name in request.names
            ]
            return tuple(item for item in resolved_imports if item is not None)
        resolved = _resolved_import(parts, module)
        if resolved is None:
            return ()
        return (
            _with_from_import_scan_paths(
                resolved, parts, request.names, roots
            ),
        )

    package_context = package_context or _package_context(importer, roots)
    if package_context is None:
        return ()

    package_root, package_parts_value = package_context
    package_parts = list(package_parts_value)
    if request.level > len(package_parts) + 1:
        return ()

    base_parts = package_parts[: len(package_parts) - request.level + 1]
    module_parts = request.module.split(".") if request.module else []
    target = base_parts + module_parts
    if target and _metadata_name(target[0]) in excluded_distributions:
        return ()
    if request.names and request.module is None:
        resolved_imports = [
            _resolved_import(parts, _resolve_module(parts, (package_root,)))
            for parts in ([*target, name] for name in request.names)
        ]
    else:
        module = _resolve_module(
            target,
            (package_root,),
            allow_bare_namespace=bool(request.names),
        )
        resolved = _resolved_import(
            target,
            module,
        )
        if resolved is None:
            resolved_imports = [
                _resolved_import(
                    [*target, name],
                    _resolve_module([*target, name], (package_root,)),
                )
                for name in request.names
            ]
        else:
            resolved_imports = [
                _with_from_import_scan_paths(
                    resolved, target, request.names, (package_root,)
                )
            ]
    return tuple(item for item in resolved_imports if item is not None)


def _resolved_import(
    parts: list[str], module: LocalModule | None
) -> _ResolvedImport | None:
    if module is None:
        return None
    return _ResolvedImport(module, _module_scan_paths(parts, module))


def _with_from_import_scan_paths(
    resolved: _ResolvedImport,
    base_parts: list[str],
    names: Sequence[str],
    roots: Sequence[Path],
) -> _ResolvedImport:
    if not names or resolved.module.kind != "package":
        return resolved

    paths = [*resolved.scan_paths]
    for name in names:
        parts = [*base_parts, name]
        module = _resolve_module(parts, roots)
        if module is not None and module.path == resolved.module.path:
            paths.extend(_module_scan_paths(parts, module))
    return _ResolvedImport(resolved.module, _dedupe_paths(paths))


def _scan_key(
    scan_path: _ScanPath,
) -> tuple[Path, Path | None, tuple[str, ...]]:
    return (
        scan_path.path.resolve(),
        scan_path.package_root.resolve()
        if scan_path.package_root is not None
        else None,
        scan_path.package_parts,
    )


def _scan_files_for_module(
    module: LocalModule, scan_paths: Sequence[_ScanPath]
) -> tuple[Path, ...]:
    if module.kind == "module":
        return (module.path,)
    return tuple(
        scan_path.path.resolve()
        for scan_path in scan_paths
        if _is_package_python_file(scan_path.path, module.path)
    )


def _resolve_module(
    parts: list[str],
    roots: Sequence[Path],
    *,
    allow_bare_namespace: bool = False,
) -> LocalModule | None:
    if not parts:
        return None

    namespace_packages: list[Path] = []
    for root in roots:
        package = root / parts[0]
        init = package / "__init__.py"
        if init.is_file():
            if not _path_in_root(package, root):
                raise LocalWheelError(
                    "Local module symlinks outside the import root are not "
                    f"supported for html-wasm local wheels: {package}"
                )
            if init.is_symlink():
                _raise_package_symlink_alias(init)
            if not _is_package_python_file(init, package):
                raise LocalWheelError(
                    "Package module symlinks outside the package root are "
                    "not supported for html-wasm local wheels: "
                    f"{init}"
                )
            if len(parts) == 1 or _package_contains(
                package,
                parts[1:],
                allow_bare_namespace=allow_bare_namespace,
            ):
                return LocalModule(
                    parts[0], package.resolve(), "package", root
                )
            return None

        module = root / f"{parts[0]}.py"
        if module.is_file():
            if not _path_in_root(module, root):
                raise LocalWheelError(
                    "Local module symlinks outside the import root are not "
                    f"supported for html-wasm local wheels: {module}"
                )
            if len(parts) == 1:
                return LocalModule(parts[0], module.resolve(), "module", root)
            return None

        if package.is_dir():
            if not _path_in_root(package, root):
                raise LocalWheelError(
                    "Local module symlinks outside the import root are not "
                    f"supported for html-wasm local wheels: {package}"
                )
            if _contains_python(package):
                namespace_packages.append(package)
            elif len(parts) > 1:
                _package_contains(
                    package,
                    parts[1:],
                    allow_bare_namespace=allow_bare_namespace,
                )

    if not namespace_packages:
        return None

    if len(namespace_packages) > 1:
        raise LocalWheelError(
            "Split namespace packages are not supported for html-wasm "
            f"local wheels: {parts[0]}"
        )

    package = namespace_packages[0]
    if len(parts) == 1:
        if allow_bare_namespace:
            return None
        raise LocalWheelError(
            "Namespace package imports must reference a concrete module for "
            f"html-wasm local wheels: {parts[0]}"
        )
    if _package_contains(
        package, parts[1:], allow_bare_namespace=allow_bare_namespace
    ):
        return LocalModule(
            parts[0], package.resolve(), "package", package.parent
        )

    return None


def _package_contains(
    package: Path, parts: list[str], *, allow_bare_namespace: bool = False
) -> bool:
    if not parts:
        return _contains_python(package)

    current = package
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        if last:
            module_file = current / f"{part}.py"
            if module_file.is_file():
                if module_file.is_symlink():
                    _raise_package_symlink_alias(module_file)
                if _is_package_python_file(module_file, package):
                    return True
                raise LocalWheelError(
                    "Package module symlinks outside the package root are "
                    "not supported for html-wasm local wheels: "
                    f"{module_file}"
                )

            child_package = current / part
            if child_package.is_dir():
                if child_package.is_symlink():
                    raise LocalWheelError(
                        "Package directory symlink aliases cannot be packaged "
                        "for html-wasm local wheels: "
                        f"{child_package}"
                    )
                if not _path_in_root(child_package, package):
                    raise LocalWheelError(
                        "Package module symlinks outside the package root "
                        "are not supported for html-wasm local wheels: "
                        f"{child_package}"
                    )
                init = child_package / "__init__.py"
                if init.is_symlink():
                    _raise_package_symlink_alias(init)
                if init.is_file() and not _is_package_python_file(
                    init, package
                ):
                    raise LocalWheelError(
                        "Package module symlinks outside the package root "
                        "are not supported for html-wasm local wheels: "
                        f"{init}"
                    )
                if not init.is_file():
                    if allow_bare_namespace:
                        return False
                    raise LocalWheelError(
                        "Namespace package imports must reference a "
                        "concrete module for html-wasm local wheels: "
                        f"{child_package}"
                    )
                return _contains_python(child_package, root=package)

            return False

        current = current / part
        if current.is_symlink():
            raise LocalWheelError(
                "Package directory symlink aliases cannot be packaged "
                "for html-wasm local wheels: "
                f"{current}"
            )
        if not current.is_dir():
            return False
        init = current / "__init__.py"
        if init.is_symlink():
            _raise_package_symlink_alias(init)
        if init.is_file() and not _is_package_python_file(init, package):
            raise LocalWheelError(
                "Package module symlinks outside the package root are "
                "not supported for html-wasm local wheels: "
                f"{init}"
            )

    return False


def _contains_python(path: Path, *, root: Path | None = None) -> bool:
    package_root = root or path
    return any(
        _is_package_python_file(child, package_root)
        for child in path.rglob("*.py")
    )


def _package_context(
    path: Path, roots: Sequence[Path]
) -> tuple[Path, list[str]] | None:
    directory = path.absolute().parent
    if (directory / "__init__.py").is_file():
        top = directory
        while (top.parent / "__init__.py").is_file():
            top = top.parent
        return top.parent, list(directory.relative_to(top.parent).parts)

    for root in sorted(
        roots, key=lambda candidate: len(candidate.parts), reverse=True
    ):
        try:
            package_parts = directory.relative_to(root).parts
        except ValueError:
            continue
        if package_parts:
            return root, list(package_parts)
    return None


def _module_python_files(module: LocalModule) -> tuple[Path, ...]:
    if module.kind == "module":
        return (module.path,)
    if module.files:
        return module.files
    init = module.path / "__init__.py"
    if init.is_file() and _is_package_python_file(init, module.path):
        return (init.resolve(),)
    return ()


def _is_package_python_file(path: Path, root: Path) -> bool:
    if path.suffix != ".py" or "__pycache__" in path.parts:
        return False
    if not _path_in_root(path, root):
        return False
    return path.is_file()


def _path_in_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _raise_package_symlink_alias(path: Path) -> None:
    raise LocalWheelError(
        "Package module symlink aliases cannot be packaged for html-wasm "
        f"local wheels: {path}"
    )


def _module_scan_paths(
    parts: list[str], module: LocalModule
) -> tuple[_ScanPath, ...]:
    if module.kind == "module":
        return (_ScanPath(module.path),)

    paths: list[_ScanPath] = []
    package_root = module.root or module.path.parent
    current = module.path
    init = current / "__init__.py"
    if init.is_file():
        if not _is_package_python_file(init, module.path):
            raise LocalWheelError(
                "Package module symlinks outside the package root are "
                "not supported for html-wasm local wheels: "
                f"{init}"
            )
        paths.append(_ScanPath(init.resolve(), package_root, tuple(parts[:1])))

    package_parts = parts[:1]
    for part in parts[1:]:
        file = current / f"{part}.py"
        if file.is_file():
            paths.append(
                _ScanPath(file.resolve(), package_root, tuple(package_parts))
            )
            break

        current = current / part
        package_parts.append(part)
        init = current / "__init__.py"
        if init.is_file():
            if not _is_package_python_file(init, module.path):
                raise LocalWheelError(
                    "Package module symlinks outside the package root are "
                    "not supported for html-wasm local wheels: "
                    f"{init}"
                )
            paths.append(
                _ScanPath(init.resolve(), package_root, tuple(package_parts))
            )

    return tuple(paths)


def _dedupe_paths(paths: Sequence[_ScanPath]) -> tuple[_ScanPath, ...]:
    seen: set[tuple[Path, Path | None, tuple[str, ...]]] = set()
    result: list[_ScanPath] = []
    for path in paths:
        key = _scan_key(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return tuple(result)


def _wheel_files(module: LocalModule) -> tuple[tuple[str, Path], ...]:
    if module.kind == "module":
        return ((f"{module.name}.py", module.path),)

    return tuple(
        (f"{module.name}/{path.relative_to(module.path).as_posix()}", path)
        for path in _module_python_files(module)
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
        dependencies.update(project.dependencies)
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
    return re.sub(r"[-_.]+", "-", name).lower()
