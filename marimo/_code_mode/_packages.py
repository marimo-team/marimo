# Copyright 2026 Marimo. All rights reserved.
"""Packages: queued package operations for `AsyncCodeModeContext`.

Accessed via :attr:`AsyncCodeModeContext.packages`. Mutations are
queued during the `async with` block and flushed on exit *before*
cell operations.
"""

from __future__ import annotations

import asyncio
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
from marimo._runtime.packages.utils import split_packages

if TYPE_CHECKING:
    from marimo._code_mode._context import AsyncCodeModeContext


@dataclass(frozen=True, slots=True)
class _AddPackage:
    package: str


@dataclass(frozen=True, slots=True)
class _RemovePackage:
    package: str


PackageOp = Union[_AddPackage, _RemovePackage]
PackageOutcome = Literal["success", "failed", "restart-required"]


@dataclass(frozen=True, slots=True)
class PackageResult:
    op: PackageOp
    outcome: PackageOutcome

    @classmethod
    def succeeded(cls, op: PackageOp) -> PackageResult:
        return cls(op, "success")

    @classmethod
    def failed(cls, op: PackageOp) -> PackageResult:
        return cls(op, "failed")

    @classmethod
    def restart_required(cls, op: PackageOp) -> PackageResult:
        return cls(op, "restart-required")


# `Packages.list` shadows the builtin in method annotations.
PackageResultList = list[PackageResult]


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

    __slots__ = ("_ctx", "_ops")

    def __init__(self, ctx: AsyncCodeModeContext) -> None:
        self._ctx = ctx
        self._ops: list[PackageOp] = []

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

    def _reset(self) -> None:
        self._ops = []

    async def _flush(self) -> PackageResultList:
        """Execute queued ops in order and retain their actual outcomes."""
        if not self._ops:
            return []

        ops = self._ops
        self._ops = []

        pm = self._ctx._kernel.packages_callbacks.package_manager
        if pm is None:
            return [PackageResult.failed(op) for op in ops]

        if not pm.is_manager_installed():
            pm.alert_not_installed()
            return [PackageResult.failed(op) for op in ops]

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
                for op in batch:
                    success = await self._run_operation(
                        op, pm, operation, manage_metadata
                    )
                    if success:
                        results.append(PackageResult.succeeded(op))
                    elif pm.restart_required:
                        results.append(PackageResult.restart_required(op))
                    else:
                        results.append(PackageResult.failed(op))

        return results

    async def _run_operation(
        self,
        op: PackageOp,
        pm: PackageManager,
        operation: EnvironmentOperationReporter,
        manage_metadata: bool,
    ) -> bool:
        pkg = op.package
        installing = isinstance(op, _AddPackage)
        operation.packages[pkg] = "running"
        operation.update(
            {pkg: f"{'Installing' if installing else 'Removing'} {pkg}...\n"},
            replace=True,
        )
        if installing:
            success = await pm.install(
                pkg,
                version=None,
                log_callback=lambda line: operation.update({pkg: line}),
            )
        else:
            success = await pm.uninstall(pkg)
        if success:
            operation.packages[pkg] = "succeeded"
            filename = self._ctx._kernel.app_metadata.filename
            if manage_metadata and filename is not None:
                await asyncio.to_thread(
                    pm.update_notebook_script_metadata,
                    filepath=filename,
                    **(
                        {"packages_to_add": split_packages(pkg)}
                        if installing
                        else {"packages_to_remove": split_packages(pkg)}
                    ),
                    upgrade=False,
                )
            message = f"Successfully {'installed' if installing else 'removed'} {pkg}\n"
        elif pm.restart_required:
            operation.packages[pkg] = "restart-required"
            message = f"Dependency changes saved for {pkg}; restart the kernel to use them.\n"
        else:
            operation.packages[pkg] = "failed"
            message = (
                f"Failed to {'install' if installing else 'remove'} {pkg}\n"
            )
        operation.update({pkg: message})
        return success
