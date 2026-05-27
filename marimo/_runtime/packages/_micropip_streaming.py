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

    Handles editable installs (`-e <path>`), direct URLs (`pkg @ url`),
    and PEP 508 environment markers (`pkg==1.0; python_version>'3.6'`).
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
    import micropip  # type: ignore[import-not-found]
    from micropip._utils import default_environment  # type: ignore[import-not-found]
    from micropip.transaction import Transaction  # type: ignore[import-not-found]
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

    # Map normalized name -> original name as the caller spelled it.
    requested = {canonicalize_name(p): p for p in packages}

    for failed_name in transaction.failed:
        normalized = canonicalize_name(failed_name)
        original = requested.pop(normalized, failed_name)
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
                original = requested.pop(normalized)
                yield (original, exc is None)

    if transaction.pyodide_packages:
        await mgr.compat_layer.loadPackage(
            mgr.compat_layer.to_js(
                [name for name, _, _ in transaction.pyodide_packages]
            )
        )
        for name, _, _ in transaction.pyodide_packages:
            normalized = canonicalize_name(name)
            if normalized in requested:
                original = requested.pop(normalized)
                yield (original, True)

    importlib.invalidate_caches()

    # Anything still in `requested` may have been pulled in transitively under
    # a different name (e.g. caller asked for `foo`, micropip installed `foo-impl`).
    # If it's importable now, treat it as installed.
    for _normalized, original in list(requested.items()):
        try:
            importlib.metadata.version(original)
            yield (original, True)
        except importlib.metadata.PackageNotFoundError:
            yield (original, False)
