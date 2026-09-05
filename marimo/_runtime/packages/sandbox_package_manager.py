# Copyright 2026 Marimo. All rights reserved.
"""Legacy package-manager adapter for a notebook sandbox.

The package endpoints and Missing packages callback still consume
`PackageManager`. This adapter keeps that compatibility surface thin while the
NotebookSandbox owns Manifest edits, synchronization, and inspection.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._environments.errors import EnvironmentManagerError
from marimo._environments.sandbox import _redact_url_credentials
from marimo._runtime.packages.package_manager import PackageDescription
from marimo._runtime.packages.pypi_package_manager import PypiPackageManager
from marimo._runtime.packages.utils import split_packages

if TYPE_CHECKING:
    from marimo._environments.sandbox import Backend, NotebookSandbox
    from marimo._runtime.packages.package_manager import LogCallback
    from marimo._utils.uv_tree import DependencyTreeNode

LOGGER = _loggers.marimo_logger()


class SandboxPackageManager(PypiPackageManager):
    """Present a NotebookSandbox through the package manager API."""

    def __init__(self, sandbox: NotebookSandbox) -> None:
        self._sandbox = sandbox
        self.name = sandbox.backend
        self.docs_url = (
            "https://pixi.sh"
            if self.name == "pixi"
            else "https://docs.astral.sh/uv/"
        )
        python = (
            sandbox.environment.python
            if sandbox.environment is not None
            else None
        )
        super().__init__(python_exe=python)

    @property
    def backend(self) -> Backend:
        return self._sandbox.backend

    def is_manager_installed(self) -> bool:
        # A running sandbox already selected this manager. Operations retain
        # their typed backend errors if the executable disappears later.
        return True

    async def _install(
        self,
        package: str,
        *,
        upgrade: bool,
        group: str | None = None,
        log_callback: LogCallback | None = None,
    ) -> bool:
        del group
        try:
            for requirement in split_packages(package):
                await asyncio.to_thread(
                    self._sandbox.add,
                    requirement,
                    upgrade=upgrade,
                    on_output=log_callback,
                )
            return True
        except EnvironmentManagerError as error:
            self._report(error, log_callback)
            return False

    async def uninstall(self, package: str, group: str | None = None) -> bool:
        del group
        try:
            for requirement in split_packages(package):
                await asyncio.to_thread(self._sandbox.remove, requirement)
            return True
        except EnvironmentManagerError as error:
            self._report(error, None)
            return False

    def list_packages(self) -> list[PackageDescription]:
        try:
            state = self._sandbox.packages()
        except EnvironmentManagerError as error:
            self._report(error, None)
            return []
        return [
            PackageDescription(name=package.name, version=package.version)
            for package in state.packages
        ]

    def dependency_tree(
        self, filename: str | None = None
    ) -> DependencyTreeNode | None:
        if filename is not None and filename != self._sandbox.source:
            self._sandbox.rebind(filename)
        try:
            return self._sandbox.packages().tree
        except EnvironmentManagerError as error:
            self._report(error, None)
            return None

    def update_notebook_script_metadata(
        self,
        filepath: str,
        *,
        packages_to_add: list[str] | None = None,
        packages_to_remove: list[str] | None = None,
        import_namespaces_to_add: list[str] | None = None,
        import_namespaces_to_remove: list[str] | None = None,
        upgrade: bool,
    ) -> bool:
        del (
            filepath,
            packages_to_add,
            packages_to_remove,
            import_namespaces_to_add,
            import_namespaces_to_remove,
            upgrade,
        )
        # add/remove already changed the Manifest and synchronized it.
        return True

    @staticmethod
    def _report(error: Exception, log_callback: LogCallback | None) -> None:
        message = _redact_url_credentials(str(error.__cause__ or error))
        LOGGER.error("Failed to update notebook sandbox: %s", message)
        if log_callback is not None:
            log_callback(message + "\n")
