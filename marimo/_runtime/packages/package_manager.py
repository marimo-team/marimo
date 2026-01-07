# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
import subprocess
import sys
from typing import TYPE_CHECKING, Callable, Optional

import msgspec

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import AlertNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.packages.utils import append_version

if TYPE_CHECKING:
    from marimo._utils.uv_tree import DependencyTreeNode

LOGGER = _loggers.marimo_logger()

# Type alias for log callback function
LogCallback = Callable[[str], None]


class PackageDescription(msgspec.Struct, rename="camel"):
    name: str
    version: str


class PackageManager(abc.ABC):
    """Interface for a package manager that can install packages."""

    name: str
    docs_url: str

    def __init__(self) -> None:
        self._attempted_packages: set[str] = set()

    @abc.abstractmethod
    def module_to_package(self, module_name: str) -> str:
        """Canonicalizes a module name to a package name."""
        ...

    @abc.abstractmethod
    def package_to_module(self, package_name: str) -> str:
        """Canonicalizes a package name to a module name."""
        ...

    def is_manager_installed(self) -> bool:
        """Is the package manager is installed on the user machine?"""
        if DependencyManager.which(self.name):
            return True
        LOGGER.error(
            f"{self.name} is not available. "
            f"Check out the docs for installation instructions: {self.docs_url}"  # noqa: E501
        )
        return False

    def install_command(
        self, package: str, *, upgrade: bool, group: Optional[str] = None
    ) -> list[str]:
        """
        Get the shell command to install a package (where applicable).

        Used by the _install method. If not applicable (for example, with micropip),
        override the _install method instead.
        """
        # PackageManager's may not implement this method if they override _install
        raise NotImplementedError

    async def _install(
        self,
        package: str,
        *,
        upgrade: bool,
        group: Optional[str] = None,
        log_callback: Optional[LogCallback] = None,
    ) -> bool:
        """Installation logic."""
        return await self.run(
            self.install_command(package, upgrade=upgrade, group=group),
            log_callback=log_callback,
        )

    async def install(
        self,
        package: str,
        version: Optional[str],
        upgrade: bool = False,
        group: Optional[str] = None,
        log_callback: Optional[LogCallback] = None,
    ) -> bool:
        """Attempt to install a package that makes this module available.

        Args:
            package: The package to install
            version: Optional version specification
            upgrade: Whether to upgrade the package if already installed
            group: Dependency group (for uv projects)
            log_callback: Optional callback to receive log output during installation

        Returns True if installation succeeded, else False.
        """
        self._attempted_packages.add(package)
        return await self._install(
            append_version(package, version),
            upgrade=upgrade,
            group=group,
            log_callback=log_callback,
        )

    @abc.abstractmethod
    async def uninstall(
        self, package: str, group: Optional[str] = None
    ) -> bool:
        """Attempt to uninstall a package

        Args:
            package: The package to uninstall
            group: dependency group

        Returns True if the package was uninstalled, else False.
        """
        ...

    def attempted_to_install(self, package: str) -> bool:
        """True iff package installation was previously attempted."""
        return package in self._attempted_packages

    def should_auto_install(self) -> bool:
        """Should this package manager auto-install packages"""
        return False

    def _run_sync(
        self, command: list[str], log_callback: Optional[LogCallback]
    ) -> bool:
        if not self.is_manager_installed():
            return False

        if log_callback is None:
            # Original behavior - just run the command without capturing output
            completed_process = subprocess.run(command)
            return completed_process.returncode == 0

        # Stream output to both the callback and the terminal
        proc = subprocess.Popen(  # noqa: ASYNC220
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=False,  # Keep as bytes to preserve ANSI codes
            bufsize=0,  # Unbuffered for real-time output
        )

        if proc.stdout:
            for line in iter(proc.stdout.readline, b""):
                # Send to terminal (original behavior)
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
                # Send to callback for streaming
                log_callback(line.decode("utf-8", errors="replace"))
            proc.stdout.close()

        return_code = proc.wait()
        return return_code == 0

    async def run(
        self, command: list[str], log_callback: Optional[LogCallback]
    ) -> bool:
        """Run a command asynchronously in a thread pool to avoid blocking the event loop."""
        import asyncio

        return await asyncio.to_thread(self._run_sync, command, log_callback)

    def update_notebook_script_metadata(
        self,
        filepath: str,
        *,
        packages_to_add: Optional[list[str]] = None,
        packages_to_remove: Optional[list[str]] = None,
        import_namespaces_to_add: Optional[list[str]] = None,
        import_namespaces_to_remove: Optional[list[str]] = None,
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
        """
        Add or remove inline script metadata metadata
        in the marimo notebook.

        For packages_to_add, packages_to_remove, we use the package name as-is.
        For import_namespaces_to_add, import_namespaces_to_remove, we canonicalize
        to the module name based on popular packages on PyPI.

        This follows PEP 723 https://peps.python.org/pep-0723/
        """
        return True

    @abc.abstractmethod
    def list_packages(self) -> list[PackageDescription]:
        """List installed packages."""
        ...

    def dependency_tree(
        self,
        filename: Optional[str] = None,  # noqa: ARG002
    ) -> Optional[DependencyTreeNode]:
        """Get dependency tree for the current environment or script.

        Args:
            filename: Optional path to a script file for script-specific dependencies

        Returns:
            DependencyTreeNode if supported by this package manager, None otherwise
        """
        return None

    def alert_not_installed(self) -> None:
        """Alert the user that the package manager is not installed."""
        broadcast_notification(
            AlertNotification(
                title="Package manager not installed",
                description=(f"{self.name} is not available on your machine."),
                variant="danger",
            ),
        )


class CanonicalizingPackageManager(PackageManager):
    """Base class for package managers.

    Has a heuristic for mapping from package names to module names and back,
    using a registry of well-known packages and basic rules for package
    names.

    Subclasses needs to implement _construct_module_name_mapping.
    """

    def __init__(self) -> None:
        # Initialized lazily
        self._module_name_to_repo_name: dict[str, str] | None = None
        self._repo_name_to_module_name: dict[str, str] | None = None
        super().__init__()

    @abc.abstractmethod
    def _construct_module_name_mapping(self) -> dict[str, str]: ...

    def _initialize_mappings(self) -> None:
        if self._module_name_to_repo_name is None:
            self._module_name_to_repo_name = (
                self._construct_module_name_mapping()
            )

        if self._repo_name_to_module_name is None:
            self._repo_name_to_module_name = {
                v: k for k, v in self._module_name_to_repo_name.items()
            }

    def module_to_package(self, module_name: str) -> str:
        """Canonicalizes a module name to a package name on PyPI."""
        if self._module_name_to_repo_name is None:
            self._initialize_mappings()
        assert self._module_name_to_repo_name is not None

        if module_name in self._module_name_to_repo_name:
            return self._module_name_to_repo_name[module_name]
        else:
            return module_name.replace("_", "-")

    def package_to_module(self, package_name: str) -> str:
        """Canonicalizes a package name to a module name."""
        if self._repo_name_to_module_name is None:
            self._initialize_mappings()
        assert self._repo_name_to_module_name is not None

        return (
            self._repo_name_to_module_name[package_name]
            if package_name in self._repo_name_to_module_name
            else package_name.replace("-", "_")
        )
