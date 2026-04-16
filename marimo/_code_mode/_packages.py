# Copyright 2026 Marimo. All rights reserved.
"""Packages: queued package operations for ``AsyncCodeModeContext``.

Accessed via :attr:`AsyncCodeModeContext.packages`. Mutations are
queued during the ``async with`` block and flushed on exit *before*
cell operations.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Union

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.notification import (
    InstallingPackageAlertNotification,
    PackageStatusType,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.packages.package_manager import PackageDescription
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
    queued during the ``async with`` block and flushed on exit *before*
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

    def add(
        self, *packages: str | list[str] | tuple[str, ...]
    ) -> None:
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

    def remove(
        self, *packages: str | list[str] | tuple[str, ...]
    ) -> None:
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

    async def _flush(self) -> list[PackageOp]:
        """Execute queued ops in order. Returns the ops that ran."""
        if not self._ops:
            return []

        ops = self._ops
        self._ops = []

        pm = self._ctx._kernel.packages_callbacks.package_manager
        if pm is None:
            return ops

        if not pm.is_manager_installed():
            pm.alert_not_installed()
            return ops

        source: Literal["kernel", "server"] = "kernel"
        statuses: PackageStatusType = {}
        for op in ops:
            if isinstance(op, _AddPackage):
                statuses[op.package] = "queued"

        if statuses:
            broadcast_notification(
                InstallingPackageAlertNotification(
                    packages=statuses, source=source
                ),
                stream=self._ctx._kernel.stream,
            )

        filename = self._ctx._kernel.app_metadata.filename
        manage_metadata = (
            GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA is True
            and filename is not None
        )

        for op in ops:
            if isinstance(op, _AddPackage):
                await self._run_add(op, pm, statuses, source, manage_metadata)
            else:
                await self._run_remove(op, pm, manage_metadata)

        return ops

    async def _run_add(
        self,
        op: _AddPackage,
        pm: Any,
        statuses: PackageStatusType,
        source: Literal["kernel", "server"],
        manage_metadata: bool,
    ) -> None:
        pkg = op.package
        statuses[pkg] = "installing"
        broadcast_notification(
            InstallingPackageAlertNotification(
                packages=statuses, source=source
            ),
            stream=self._ctx._kernel.stream,
        )
        broadcast_notification(
            InstallingPackageAlertNotification(
                packages=statuses,
                logs={pkg: f"Installing {pkg}...\n"},
                log_status="start",
                source=source,
            ),
            stream=self._ctx._kernel.stream,
        )

        def log_callback(log_line: str) -> None:
            broadcast_notification(
                InstallingPackageAlertNotification(
                    packages=statuses,
                    logs={pkg: log_line},
                    log_status="append",
                    source=source,
                ),
                stream=self._ctx._kernel.stream,
            )

        success = await pm.install(
            pkg, version=None, log_callback=log_callback
        )
        if success:
            statuses[pkg] = "installed"
            final_log = f"Successfully installed {pkg}\n"
            if manage_metadata:
                await asyncio.to_thread(
                    pm.update_notebook_script_metadata,
                    filepath=self._ctx._kernel.app_metadata.filename,
                    packages_to_add=split_packages(pkg),
                    upgrade=False,
                )
        else:
            statuses[pkg] = "failed"
            final_log = f"Failed to install {pkg}\n"

        broadcast_notification(
            InstallingPackageAlertNotification(
                packages=statuses,
                logs={pkg: final_log},
                log_status="done",
                source=source,
            ),
            stream=self._ctx._kernel.stream,
        )

    async def _run_remove(
        self,
        op: _RemovePackage,
        pm: Any,
        manage_metadata: bool,
    ) -> None:
        success = await pm.uninstall(op.package)
        if success and manage_metadata:
            await asyncio.to_thread(
                pm.update_notebook_script_metadata,
                filepath=self._ctx._kernel.app_metadata.filename,
                packages_to_remove=split_packages(op.package),
                upgrade=False,
            )
