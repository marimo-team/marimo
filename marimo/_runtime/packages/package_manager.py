# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import Alert
from marimo._runtime.packages.utils import append_version

LOGGER = _loggers.marimo_logger()


@dataclass
class PackageDescription:
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

    @abc.abstractmethod
    async def _install(self, package: str) -> bool:
        """Installation logic."""
        ...

    async def install(self, package: str, version: Optional[str]) -> bool:
        """Attempt to install a package that makes this module available.

        Returns True if installation succeeded, else False.
        """
        self._attempted_packages.add(package)
        return await self._install(append_version(package, version))

    @abc.abstractmethod
    async def uninstall(self, package: str) -> bool:
        """Attempt to uninstall a package

        Returns True if the package was uninstalled, else False.
        """
        ...

    def attempted_to_install(self, package: str) -> bool:
        """True iff package installation was previously attempted."""
        return package in self._attempted_packages

    def should_auto_install(self) -> bool:
        """Should this package manager auto-install packages"""
        return False

    def run(self, command: list[str]) -> bool:
        if not self.is_manager_installed():
            return False
        proc = subprocess.run(command)  # noqa: ASYNC101
        return proc.returncode == 0

    def update_notebook_script_metadata(
        self,
        filepath: str,
        import_namespaces_to_add: List[str],
        import_namespaces_to_remove: List[str],
    ) -> None:
        del filepath, import_namespaces_to_add, import_namespaces_to_remove
        """
        Add or remove inline script metadata metadata
        in the marimo notebook.

        This follows PEP 723 https://peps.python.org/pep-0723/
        """
        return

    @abc.abstractmethod
    def list_packages(self) -> List[PackageDescription]:
        """List installed packages."""
        ...

    def alert_not_installed(self) -> None:
        """Alert the user that the package manager is not installed."""
        Alert(
            title="Package manager not installed",
            description=(f"{self.name} is not available on your machine."),
            variant="danger",
        ).broadcast()


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
