# Copyright 2026 Marimo. All rights reserved.
# This module is intentionally marimo-free so it can be contributed
# back to pyodide/micropip as a streaming install primitive.
# Do NOT import from marimo.* here.
from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
from pathlib import Path
from site import getsitepackages
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _append_version(pkg_name: str, version: str | None) -> str:
    """Qualify a version string with a leading '==' if it doesn't have one."""
    if version is None or version in ("", "latest"):
        return pkg_name
    return f"{pkg_name}=={version}"


def _split_packages(package: str) -> list[str]:
    """Split a whitespace-joined package spec into individual requirements.

    Each individual requirement follows PEP 508 dependency-specification
    grammar (https://peps.python.org/pep-0508/) — version specifiers, direct
    URL references (`pkg @ url`), and environment markers
    (`pkg==1.0; python_version>'3.6'`). The whitespace-joined list and the
    `-e`/`--editable` prefix mirror pip's requirement-specifier syntax
    (https://pip.pypa.io/en/stable/reference/requirement-specifiers/).
    """
    packages: list[str] = []
    current: list[str] = []
    in_marker = False

    for part in package.split():
        if (
            part in ("-e", "--editable", "@")
            or current
            and current[-1] in ("-e", "--editable", "@")
        ):
            current.append(part)
        elif part.endswith(";"):
            if current:
                packages.append(" ".join(current))
                current = []
            in_marker = True
            current.append(part)
        elif in_marker:
            current.append(part)
            if part.endswith(("'", '"')):
                in_marker = False
                packages.append(" ".join(current))
                current = []
        else:
            if current:
                packages.append(" ".join(current))
            current = [part]

    if current:
        packages.append(" ".join(current))

    return [pkg.strip() for pkg in packages]


async def stream_transaction_install(
    packages: list[str],
    *,
    versions: dict[str, str | None] | None = None,
    index_urls: list[str] | None = None,
    constraints: list[str] | None = None,
) -> AsyncIterator[tuple[str, bool]]:
    """Install via micropip's Transaction API, yielding (name, success) per wheel.

    Mirrors what `micropip.install()` does internally, but exposes the resolved
    wheel list so callers can stream progress as each wheel finishes installing
    (via `asyncio.as_completed`) instead of waiting for an opaque end-to-end call.

    `index_urls` and `constraints`, when None, fall back to the values on
    `micropip._micropip` (the global singleton); when provided, they override
    the singleton for this transaction only.

    Yields `(package_name, success)` per requested package. Packages that
    resolve to native pyodide-distribution entries are loaded via
    `loadPackage`; pure-python wheels are downloaded and extracted in parallel.
    """
    # Lazy / dynamic import so this module loads cleanly outside Pyodide
    # (where micropip isn't installed). A ModuleNotFoundError here propagates
    # as ImportError, which the marimo-side wrapper catches and falls back.
    micropip = importlib.import_module("micropip")
    default_environment = importlib.import_module(
        "micropip._utils"
    ).default_environment
    Transaction = importlib.import_module("micropip.transaction").Transaction
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    mgr = micropip._micropip  # singleton PackageManager
    ctx = default_environment()
    wheel_base = Path(getsitepackages()[0])

    flat_requirements: list[str] = []
    for pkg in packages:
        version = (versions or {}).get(pkg)
        versioned = _append_version(pkg, version)
        flat_requirements.extend(_split_packages(versioned))

    transaction = Transaction(
        _compat_layer=mgr.compat_layer,
        ctx=ctx,
        ctx_extras=[],
        keep_going=True,
        deps=True,
        pre=False,
        fetch_kwargs={},
        verbose=False,
        index_urls=index_urls if index_urls is not None else mgr.index_urls,
        constraints=constraints
        if constraints is not None
        else mgr.constraints,
        reinstall=False,
    )

    await transaction.gather_requirements(flat_requirements)

    # Map normalized base-package-name -> (original spec, base name). The
    # caller's strings may include version specifiers, URL specs, or markers
    # (`foo==1.0`, `foo @ git+…@ref`, `foo; python_version>'3.10'`), so parse
    # out the base name before canonicalizing — otherwise the wheel name
    # micropip yields back ("foo") will fail to match the spec string. We keep
    # both: `original` is what we report back to the caller (their spelling),
    # `base_name` is the bare distribution name for `importlib.metadata`.
    requested: dict[str, tuple[str, str]] = {}
    for spec in packages:
        try:
            base_name = Requirement(spec).name
        except Exception:
            # Editable/path specs and other oddities Requirement can't parse;
            # fall back to canonicalizing the whole string. Worst case it
            # gets reconciled by the importlib.metadata pass at the end.
            base_name = spec
        requested[canonicalize_name(base_name)] = (spec, base_name)

    for failed_name in transaction.failed:
        normalized = canonicalize_name(failed_name)
        original, _ = requested.pop(normalized, (failed_name, failed_name))
        yield (original, False)

    async def _install_wheel(wheel: Any) -> tuple[str, Exception | None]:
        try:
            await wheel.install(wheel_base, mgr.compat_layer)
        except Exception as exc:
            return wheel.name, exc
        return wheel.name, None

    if transaction.wheels:
        tasks = [
            asyncio.create_task(_install_wheel(w)) for w in transaction.wheels
        ]
        for future in asyncio.as_completed(tasks):
            name, exc = await future
            normalized = canonicalize_name(name)
            if normalized in requested:
                original, _ = requested.pop(normalized)
                yield (original, exc is None)

    if transaction.pyodide_packages:
        names = [name for name, _, _ in transaction.pyodide_packages]
        try:
            await mgr.compat_layer.loadPackage(mgr.compat_layer.to_js(names))
        except Exception:
            load_succeeded = False
        else:
            load_succeeded = True
        for name in names:
            normalized = canonicalize_name(name)
            if normalized in requested:
                original, _ = requested.pop(normalized)
                yield (original, load_succeeded)

    importlib.invalidate_caches()

    # Anything still in `requested` may have been pulled in transitively under
    # a different name (e.g. caller asked for `foo`, micropip installed `foo-impl`).
    # If it's importable now, treat it as installed. Look up the bare base name,
    # not the caller's spec — `importlib.metadata.version` expects a
    # distribution name and would raise on `foo==1.0`, `foo @ git+…`, or markers.
    for _normalized, (original, base_name) in list(requested.items()):
        try:
            importlib.metadata.version(base_name)
            yield (original, True)
        except importlib.metadata.PackageNotFoundError:
            yield (original, False)
