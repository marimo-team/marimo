# Copyright 2026 Marimo. All rights reserved.
"""Packages: queued package operations for `AsyncCodeModeContext`.

Accessed via :attr:`AsyncCodeModeContext.packages`. Mutations are
queued during the `async with` block and flushed on exit *before*
cell operations.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass
from functools import partial
from itertools import groupby
from typing import TYPE_CHECKING, Literal, Union

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.notification import (
    EnvironmentAction,
    PackageStatusType,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.packages.operations import (
    EnvironmentOperationReporter,
    environment_operation,
)
from marimo._runtime.packages.package_manager import (
    PackageDescription,
    PackageManager,
)
from marimo._runtime.packages.utils import run_package_command, split_packages

if TYPE_CHECKING:
    from marimo._code_mode._context import AsyncCodeModeContext


@dataclass(frozen=True, slots=True)
class _AddPackage:
    package: str


@dataclass(frozen=True, slots=True)
class _RemovePackage:
    package: str


PackageOp = Union[_AddPackage, _RemovePackage]
PackageOpList = list[PackageOp]
ModuleList = list[str]
PackageOutcome = Literal["success", "failed", "restart-required"]


@dataclass(frozen=True, slots=True)
class PackageResult:
    action: Literal["add", "remove"]
    package: str
    outcome: PackageOutcome

    @classmethod
    def succeeded(cls, op: PackageOp) -> PackageResult:
        return cls(_action(op), op.package, "success")

    @classmethod
    def failed(cls, op: PackageOp) -> PackageResult:
        return cls(_action(op), op.package, "failed")

    @classmethod
    def restart_required(cls, op: PackageOp) -> PackageResult:
        return cls(_action(op), op.package, "restart-required")


def _action(op: PackageOp) -> Literal["add", "remove"]:
    return "add" if isinstance(op, _AddPackage) else "remove"


# `Packages.list` shadows the builtin in method annotations.
PackageResultList = list[PackageResult]


@dataclass(frozen=True, slots=True)
class PackageImportCheck:
    """Result of importing one module in a fresh Python interpreter."""

    module: str
    success: bool
    origin: str | None = None
    is_namespace: bool | None = None
    distributions: tuple[str, ...] = ()
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


_FRESH_IMPORT_CHECK_PROGRAM = """
import contextlib
import importlib
import importlib.metadata
import io
import json
import sys

results = []
distributions = importlib.metadata.packages_distributions()
for name in json.loads(sys.argv[1]):
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            module = importlib.import_module(name)
        spec = module.__spec__
        results.append({
            "module": name,
            "success": True,
            "origin": None if spec is None else spec.origin,
            "is_namespace": bool(spec is not None and spec.origin is None),
            "distributions": distributions.get(name.split(".")[0], []),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        })
    except BaseException as error:
        results.append({
            "module": name,
            "success": False,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "error": f"{type(error).__name__}: {error}",
        })
print(json.dumps(results))
"""


def _verify_imports_in_fresh_process(
    modules: list[str],
) -> list[PackageImportCheck]:
    try:
        completed = run_package_command(
            [
                sys.executable,
                "-c",
                _FRESH_IMPORT_CHECK_PROGRAM,
                json.dumps(modules),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        message = f"{type(error).__name__}: {error}"
        return [
            PackageImportCheck(module=module, success=False, error=message)
            for module in modules
        ]

    if completed.returncode != 0:
        message = (
            completed.stderr.strip() or "Fresh interpreter verification failed"
        )
        return [
            PackageImportCheck(module=module, success=False, error=message)
            for module in modules
        ]

    try:
        raw_results = json.loads(completed.stdout)
        return [
            PackageImportCheck(
                module=result["module"],
                success=result["success"],
                origin=result.get("origin"),
                is_namespace=result.get("is_namespace"),
                distributions=tuple(result.get("distributions", ())),
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                error=result.get("error"),
            )
            for result in raw_results
        ]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        message = f"Invalid verification response: {error}"
        return [
            PackageImportCheck(module=module, success=False, error=message)
            for module in modules
        ]


def _flatten_packages(
    packages: tuple[str | list[str] | tuple[str, ...], ...],
) -> list[str]:
    """Flatten a mix of strings and lists/tuples of strings."""
    result: list[str] = []
    for pkg in packages:
        if isinstance(pkg, (list, tuple)):
            result.extend(pkg)
        else:
            result.append(pkg)
    return result


class Packages:
    """Package management for the running notebook's environment.

    Accessed as :attr:`AsyncCodeModeContext.packages`. Mutations are
    queued during the `async with` block and flushed on exit *before*
    cell operations, so newly added cells can import newly installed
    packages.

    Examples:
        ```python
        async with cm.get_context() as ctx:
            ctx.packages.add("pandas", "numpy>=1.26")
            ctx.packages.remove("old-package")
            cid = ctx.create_cell("import pandas as pd")
            ctx.run_cell(cid)
        ```

    :meth:`list` returns the currently installed packages and must be
    called before any :meth:`add` or :meth:`remove` in the same batch.
    """

    __slots__ = ("_ctx", "_ops", "_results")

    def __init__(self, ctx: AsyncCodeModeContext) -> None:
        self._ctx = ctx
        self._ops: PackageOpList = []
        self._results: PackageResultList = []

    @property
    def results(self) -> tuple[PackageResult, ...]:
        """Outcomes from the most recently flushed package batch."""
        return tuple(self._results)

    def add(self, *packages: str | list[str] | tuple[str, ...]) -> None:
        """Queue packages for installation on context exit.

        Packages are installed with streaming UI notifications and the
        script metadata is updated for sandboxed notebooks. Cells are
        *not* automatically re-run — use :meth:`run_cell` for that.

        Examples:
            ```python
            ctx.packages.add("pandas")
            ctx.packages.add("polars>=0.20", "numpy==1.26")
            ctx.packages.add(["altair", "vega_datasets"])
            ```

        Args:
            *packages: Pip-style package specifiers. Accepts individual
                strings, or a list/tuple of strings.
        """
        self._ctx._require_entered()
        for pkg in _flatten_packages(packages):
            self._ops.append(_AddPackage(package=pkg))

    def remove(self, *packages: str | list[str] | tuple[str, ...]) -> None:
        """Queue packages for removal on context exit.

        Updates the script metadata for sandboxed notebooks.

        Examples:
            ```python
            ctx.packages.remove("pandas")
            ctx.packages.remove("old-pkg", "another-pkg")
            ctx.packages.remove(["altair", "vega_datasets"])
            ```

        Args:
            *packages: Package names to uninstall. Accepts individual
                strings, or a list/tuple of strings.
        """
        self._ctx._require_entered()
        for pkg in _flatten_packages(packages):
            self._ops.append(_RemovePackage(package=pkg))

    def list(self) -> list[PackageDescription]:
        """Return currently installed packages.

        Raises:
            RuntimeError: If :meth:`add` or :meth:`remove` has already
                been called in this batch. Queued operations haven't
                executed yet, so listing would return stale state.
                Exit the context to flush them first, then start a new
                batch.
        """
        if self._ops:
            raise RuntimeError(
                "Cannot call ctx.packages.list() after add/remove have "
                "been queued — pending operations have not been applied "
                "yet. Exit the context to flush them first, then start "
                "a new batch."
            )
        pm = self._ctx._kernel.packages_callbacks.package_manager
        if pm is None:
            return []
        return pm.list_packages()

    async def verify_imports(
        self, modules: ModuleList
    ) -> tuple[PackageImportCheck, ...]:
        """Import modules in a fresh interpreter and report their origins."""
        self._ctx._require_entered()
        if self._ops:
            raise RuntimeError(
                "Cannot verify imports while package operations are pending. "
                "Exit this context to apply them, then verify in a new one."
            )
        checks = await asyncio.to_thread(
            _verify_imports_in_fresh_process, modules
        )
        return tuple(checks)

    def _reset(self) -> None:
        self._ops = []
        self._results = []

    async def _flush(self) -> PackageResultList:
        """Execute queued ops in order and retain their actual outcomes."""
        if not self._ops:
            self._results = []
            return []

        ops = self._ops
        self._ops = []

        pm = self._ctx._kernel.packages_callbacks.package_manager
        if pm is None:
            self._results = [PackageResult.failed(op) for op in ops]
            return self._results

        if not pm.is_manager_installed():
            pm.alert_not_installed()
            self._results = [PackageResult.failed(op) for op in ops]
            return self._results

        filename = self._ctx._kernel.app_metadata.filename
        manage_metadata = (
            GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA is True
            and filename is not None
        )
        results: PackageResultList = []
        # Group adjacent actions so progress stays in package alerts without
        # reordering an add/remove/add sequence.
        for installing, group in groupby(
            ops, key=lambda op: isinstance(op, _AddPackage)
        ):
            batch = list(group)
            statuses: PackageStatusType = {
                op.package: "queued" for op in batch
            }
            action: EnvironmentAction = "install" if installing else "remove"
            with environment_operation(
                action,
                statuses,
                "kernel",
                partial(
                    broadcast_notification, stream=self._ctx._kernel.stream
                ),
            ) as operation:
                success = await self._run_batch(
                    batch, pm, operation, manage_metadata
                )
                for op in batch:
                    if success:
                        results.append(PackageResult.succeeded(op))
                    elif pm.restart_required:
                        results.append(PackageResult.restart_required(op))
                    else:
                        results.append(PackageResult.failed(op))

        self._results = results
        return results

    async def _run_batch(
        self,
        ops: PackageOpList,
        pm: PackageManager,
        operation: EnvironmentOperationReporter,
        manage_metadata: bool,
    ) -> bool:
        assert ops
        installing = isinstance(ops[0], _AddPackage)
        packages = [op.package for op in ops]
        for package in packages:
            operation.packages[package] = "running"
        operation.update(
            {
                package: (
                    f"{'Installing' if installing else 'Removing'} "
                    f"{package}...\n"
                )
                for package in packages
            },
            replace=True,
        )
        if installing:
            success = await pm.install_many(
                packages,
                log_callback=lambda line: operation.update(
                    dict.fromkeys(packages, line)
                ),
            )
        else:
            success = await pm.uninstall_many(packages)
        status: Literal["succeeded", "restart-required", "failed"] = (
            "succeeded"
            if success
            else "restart-required"
            if pm.restart_required
            else "failed"
        )
        for package in packages:
            operation.packages[package] = status
        if success:
            filename = self._ctx._kernel.app_metadata.filename
            if manage_metadata and filename is not None:
                await asyncio.to_thread(
                    pm.update_notebook_script_metadata,
                    filepath=filename,
                    **(
                        {
                            "packages_to_add": [
                                requirement
                                for package in packages
                                for requirement in split_packages(package)
                            ]
                        }
                        if installing
                        else {
                            "packages_to_remove": [
                                requirement
                                for package in packages
                                for requirement in split_packages(package)
                            ]
                        }
                    ),
                    upgrade=False,
                )
            message = (
                f"Successfully {'installed' if installing else 'removed'}"
            )
        elif pm.restart_required:
            message = (
                "Dependency changes saved; restart the kernel to use them"
            )
        else:
            message = f"Failed to {'install' if installing else 'remove'}"
        operation.update(
            {package: f"{message} {package}\n" for package in packages}
        )
        return success
