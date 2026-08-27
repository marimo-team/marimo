# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._environments import script_metadata
from marimo._environments.uv import UvCommandError, find_uv_bin, uv
from marimo._runtime.packages._micropip_streaming import (
    stream_transaction_install,
)
from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)
from marimo._runtime.packages.package_manager import (
    CanonicalizingPackageManager,
    LogCallback,
    PackageDescription,
)
from marimo._runtime.packages.utils import (
    popen_package_command,
    run_package_command,
    split_packages,
)
from marimo._utils.platform import is_pyodide
from marimo._utils.uv_tree import DependencyTreeNode, parse_uv_tree
from marimo._utils.versions import (
    extract_extras,
    has_version_specifier,
    without_extras,
    without_version_specifier,
)

PY_EXE = sys.executable

LOGGER = _loggers.marimo_logger()


class VersionMap:
    """
    A map of package names to versions, with some extra
    logic for defensibility when checking if a package is installed.
    """

    def __init__(self, version_map: dict[str, str]) -> None:
        self.version_map = version_map

    def get_version(self, package: str) -> str | None:
        """Get the version of a package."""
        # Remove extras and version specifier
        package = without_extras(without_version_specifier(package)).lower()
        return (
            self._get(package)
            # Try replacing _ with - and - with _
            or self._get(package.replace("_", "-"))
            or self._get(package.replace("-", "_"))
        )

    def resolve_with_version(self, package: str) -> str | None:
        """Resolve a package name to a package name with a version specifier.

        Preserves extras from the original package name in the result.
        For example: 'requests[security]' -> 'requests[security]==2.28.0'
        """
        # Extract and preserve extras
        extras = extract_extras(without_version_specifier(package))

        # Get the base package name without extras or version specifier
        base_package = without_extras(
            without_version_specifier(package)
        ).lower()

        # Try exact match
        if base_package in self.version_map:
            return f"{base_package}{extras}=={self.version_map[base_package]}"

        # Try replacing _ with -
        normalized_package = base_package.replace("_", "-")
        if normalized_package in self.version_map:
            return f"{normalized_package}{extras}=={self.version_map[normalized_package]}"

        # Try replacing - with _
        normalized_package = base_package.replace("-", "_")
        if normalized_package in self.version_map:
            return f"{normalized_package}{extras}=={self.version_map[normalized_package]}"

        return None

    def _get(self, package: str) -> str | None:
        return self.version_map.get(package)

    def has(self, package: str) -> bool:
        return self.get_version(package) is not None


class PypiPackageManager(CanonicalizingPackageManager):
    def _construct_module_name_mapping(self) -> dict[str, str]:
        return module_name_to_pypi_name()

    def _list_packages_from_cmd(
        self, cmd: list[str]
    ) -> list[PackageDescription]:
        if not self.is_manager_installed():
            return []
        proc = run_package_command(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            return []
        try:
            packages = json.loads(proc.stdout)
            return [
                PackageDescription(name=pkg["name"], version=pkg["version"])
                for pkg in packages
            ]
        except json.JSONDecodeError:
            return []


class PipPackageManager(PypiPackageManager):
    name = "pip"
    docs_url = "https://pip.pypa.io/"

    def is_manager_installed(self) -> bool:
        """Check if pip is available.

        On some platforms (e.g. macOS with pip-installed Python from python.org),
        only `pip3` is available in PATH, not `pip`. We first try the method we
        actually use to invoke pip (`python -m pip`), then fall back to a PATH
        check for compatibility.
        """
        # Primary check: use the same invocation method we actually use
        # (python -m pip) rather than relying on PATH pip, which could be
        # a different Python's pip than self._python_exe
        try:
            proc = run_package_command(
                [self._python_exe, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        # Fallback: check if pip is on PATH (handles cases where pip is
        # available but python -m pip is not desired/needed)
        if DependencyManager.which(self.name):
            return True
        LOGGER.error(
            f"{self.name} is not available. "
            f"Check out the docs for installation instructions: {self.docs_url}"
        )
        return False

    def install_command(
        self, package: str, *, upgrade: bool, group: str | None = None
    ) -> list[str]:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        return [
            self._python_exe,
            "-m",
            "pip",
            "install",
            *(["--upgrade"] if upgrade else []),
            *split_packages(package),
        ]

    async def uninstall(self, package: str, group: str | None = None) -> bool:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        LOGGER.info(f"Uninstalling {package} with pip")
        return await self.run(
            [
                self._python_exe,
                "-m",
                "pip",
                "uninstall",
                "-y",
                *split_packages(package),
            ],
            log_callback=None,
        )

    def list_packages(self) -> list[PackageDescription]:
        cmd = [
            self._python_exe,
            "-m",
            "pip",
            "list",
            "--format=json",
        ]
        return self._list_packages_from_cmd(cmd)


class MicropipPackageManager(PypiPackageManager):
    name = "micropip"
    docs_url = "https://micropip.pyodide.org/"

    def should_auto_install(self) -> bool:
        # We don't auto-install packages with micropip without the user's consent,
        # since it can install unwanted packages.
        return False

    def is_manager_installed(self) -> bool:
        return is_pyodide()

    async def _install(
        self,
        package: str,
        *,
        upgrade: bool,
        group: str | None = None,
        log_callback: LogCallback | None = None,
    ) -> bool:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        assert is_pyodide()
        import micropip  # type: ignore

        # If we're upgrading, we need to uninstall the package first
        # to avoid conflicts
        if upgrade:
            try:
                await micropip.uninstall(split_packages(package))
            except ValueError:
                pass

        try:
            if log_callback:
                log_callback(f"Installing {package} with micropip...\n")
            await micropip.install(split_packages(package))
            if log_callback:
                log_callback(f"Successfully installed {package}\n")
            return True
        except ValueError as e:
            if log_callback:
                log_callback(f"Failed to install {package}: {e}\n")
            return False

    async def stream_install(
        self,
        packages: list[str],
        *,
        versions: dict[str, str | None] | None = None,
        index_urls: list[str] | None = None,
        log_callback_factory: Callable[[str], LogCallback] | None = None,
    ) -> AsyncIterator[tuple[str, bool]]:
        """Batch-install via micropip Transaction internals, streaming progress.

        Wraps `stream_transaction_install` with marimo bookkeeping
        (`_attempted_packages`) and log-callback glue.  Falls back to the
        base sequential path if micropip's internal API has shifted.
        """
        assert is_pyodide()

        if log_callback_factory:
            for pkg in packages:
                log_callback_factory(pkg)(f"Resolving {pkg}...\n")

        yielded: set[str] = set()
        try:
            async for pkg, success in stream_transaction_install(
                packages,
                versions=versions,
                index_urls=index_urls,
            ):
                # Mark only as the engine resolves each package — if the
                # engine raises before any yields, the fallback path needs
                # to start clean (it will mark via `install()`).
                self._attempted_packages.add(pkg)
                yielded.add(pkg)
                if log_callback_factory:
                    msg = (
                        f"Successfully installed {pkg}\n"
                        if success
                        else f"Failed to install {pkg}\n"
                    )
                    log_callback_factory(pkg)(msg)
                yield (pkg, success)
        except (AttributeError, ImportError, TypeError):
            # micropip's private Transaction API shifted; fall back to the
            # base sequential path.  Narrow catch: install errors should
            # surface, only API-shape mismatches trigger the fallback.
            LOGGER.warning(
                "micropip Transaction API unavailable, falling back to sequential installs",
                exc_info=True,
            )
            remaining = [p for p in packages if p not in yielded]
            async for result in super().stream_install(
                remaining,
                versions=versions,
                index_urls=index_urls,
                log_callback_factory=log_callback_factory,
            ):
                yield result

    async def uninstall(self, package: str, group: str | None = None) -> bool:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        assert is_pyodide()
        import micropip  # type: ignore

        try:
            micropip.uninstall(package)
            return True
        except ValueError:
            return False

    def list_packages(self) -> list[PackageDescription]:
        assert is_pyodide()
        import micropip  # type: ignore

        packages = [
            PackageDescription(name=pkg.name, version=pkg.version)
            for pkg in micropip.list()
        ]
        # micropip doesn't sort the packages
        return sorted(packages, key=lambda pkg: pkg.name)

    def check_available(self) -> bool:
        return is_pyodide()


class UvPackageManager(PypiPackageManager):
    name = "uv"
    docs_url = "https://docs.astral.sh/uv/"

    SCRIPT_METADATA_MARKER = "# /// script"
    _use_project = True

    @classmethod
    def for_pip_install(cls, python_exe: str) -> UvPackageManager:
        """Target an interpreter without changing its uv project."""
        manager = cls(python_exe=python_exe)
        manager._use_project = False
        return manager

    @cached_property
    def _uv_bin(self) -> str:
        return find_uv_bin()

    def _is_cache_write_error(self, output_text: str) -> bool:
        """Check if the output text indicates a cache write error.

        This is somewhat fragile and could break with new uv output.
        This was tested with uv ~0.9.7
        """
        output_text = output_text.lower()
        return (
            "failed to write to the distribution cache" in output_text
            or "operation not permitted" in output_text
        )

    def is_manager_installed(self) -> bool:
        return self._uv_bin != "uv" or super().is_manager_installed()

    def install_command(
        self, package: str, *, upgrade: bool, group: str | None = None
    ) -> list[str]:
        install_cmd: list[str]
        if self.is_in_uv_project:
            install_cmd = [self._uv_bin, "add"]
            if group:
                install_cmd.extend(["--group", group])
        else:
            install_cmd = [self._uv_bin, "pip", "install"]

            # Allow for explicit site directory location if needed
            target = os.environ.get("MARIMO_UV_TARGET", None)
            if target:
                install_cmd.append(f"--target={target}")

        if upgrade:
            install_cmd.append("--upgrade")

        return install_cmd + [
            # we don't set --compile-bytecode or --no-compile-bytecode because we want
            # to respect the user's env (e.g. UV_COMPILE_BYTECODE)
            *split_packages(package),
            "-p",
            self._python_exe,
        ]

    async def _install(
        self,
        package: str,
        *,
        upgrade: bool,
        group: str | None = None,
        log_callback: LogCallback | None = None,
    ) -> bool:
        """Installation logic with fallback to --no-cache on cache write errors."""
        LOGGER.info(
            f"Installing in {package} with 'uv {'add' if self.is_in_uv_project else 'pip install'}'"
        )

        # For uv projects, use the standard install flow without fallback
        if self.is_in_uv_project:
            return await super()._install(
                package,
                upgrade=upgrade,
                group=group,
                log_callback=log_callback,
            )

        import asyncio

        return await asyncio.to_thread(
            self._install_with_cache_fallback,
            package,
            upgrade=upgrade,
            group=group,
            log_callback=log_callback,
        )

    def _install_with_cache_fallback(
        self,
        package: str,
        *,
        upgrade: bool,
        group: str | None,
        log_callback: LogCallback | None,
    ) -> bool:
        cmd = self.install_command(package, upgrade=upgrade, group=group)

        LOGGER.info(f"Running command: {cmd}")

        # Run the command and capture output
        proc = popen_package_command(cmd)

        if proc is None:
            return False

        output_lines: list[str] = []
        if proc.stdout:
            for line in iter(proc.stdout.readline, b""):
                # Send to terminal
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
                decoded_line = line.decode("utf-8", errors="replace")
                # Send to callback for streaming
                if log_callback:
                    log_callback(decoded_line)
                # Store for error checking
                output_lines.append(decoded_line)
            proc.stdout.close()

        return_code = proc.wait()

        # If successful, we're done
        if return_code == 0:
            return True

        # Check if we should retry with --no-cache
        output_text = "".join(output_lines)
        if self._is_cache_write_error(output_text):
            LOGGER.info(
                f"Retrying installation of {package} with --no-cache due to cache write error"
            )
            if log_callback:
                log_callback(
                    "\nRetrying with --no-cache due to cache write permission error...\n"
                )

            return self._run_sync(
                cmd + ["--no-cache"],
                log_callback=log_callback,
            )

        return False

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
        """Update the notebook's script metadata with the packages to add/remove.

        Args:
            filepath: Path to the notebook file
            packages_to_add: List of packages to add to the script metadata
            packages_to_remove: List of packages to remove from the script metadata
            import_namespaces_to_add: List of import namespaces to add
            import_namespaces_to_remove: List of import namespaces to remove
            upgrade: Whether to upgrade the packages
        """
        packages_to_add = packages_to_add or []
        packages_to_remove = packages_to_remove or []
        import_namespaces_to_add = import_namespaces_to_add or []
        import_namespaces_to_remove = import_namespaces_to_remove or []

        packages_to_add = packages_to_add + [
            self.module_to_package(im) for im in import_namespaces_to_add
        ]
        packages_to_remove = packages_to_remove + [
            self.module_to_package(im) for im in import_namespaces_to_remove
        ]

        if not packages_to_add and not packages_to_remove:
            return True

        LOGGER.info(f"Updating script metadata for {filepath}")

        version_map = self._get_version_map()

        def _is_direct_reference(package: str) -> bool:
            """Check if a package is a direct reference (git, URL, or local path).

            Direct references should bypass the _is_installed check because:
            - Git URLs (git+https://...) won't appear in version_map with that prefix
            - Direct URL references (package @ https://...) use @ syntax
            - Local paths (package @ file://...) use @ syntax
            - These should be passed directly to uv which handles them correctly
            """
            # Git URLs: git+https://, git+ssh://, git://
            if package.startswith(("git+", "git://")):
                return True
            # Direct references with @ (PEP 440 direct references)
            if " @ " in package:
                return True
            # URLs (https://, http://, file://)
            return "://" in package

        def _is_installed(package: str) -> bool:
            return version_map.has(package)

        def _maybe_add_version(package: str) -> str:
            # Skip marimo and marimo[<mod>], but not marimo-<something-else>
            if package == "marimo" or package.startswith("marimo["):
                return package
            if has_version_specifier(package):
                return package
            return version_map.resolve_with_version(package) or package

        # Filter to packages that are found in "uv pip list" OR are direct references
        # Direct references (git URLs, direct URLs, local paths) bypass the installed check
        # because they won't appear in the version map with their full reference syntax
        packages_to_add = [
            _maybe_add_version(im) if not _is_direct_reference(im) else im
            for im in packages_to_add
            if _is_direct_reference(im) or _is_installed(im)
        ]

        try:
            script_metadata.add_dependencies(
                filepath, packages_to_add, upgrade=upgrade
            )
            script_metadata.remove_dependencies(filepath, packages_to_remove)
        except script_metadata.ScriptMetadataError as e:
            LOGGER.warning(
                f"Failed to update script metadata for {filepath}: {e}"
            )
            return False
        return True

    def _get_version_map(self) -> VersionMap:
        packages = self.list_packages()
        return VersionMap({pkg.name: pkg.version for pkg in packages})

    # Only needs to run once per session
    @cached_property
    def is_in_uv_project(self) -> bool:
        """Determine if we are currently running marimo from a uv project

        A [uv project](https://docs.astral.sh/uv/concepts/projects/layout/) contains a
        pyproject.toml and a uv.lock file.

        We can determine if we are in a uv project AND using this project's virtual environment
        by checking:
        - The "UV" environment variable is set
        - The "VIRTUAL_ENV" environment variable is set
        - The "uv.lock" file exists where the "VIRTUAL_ENV" is
        - The "pyproject.toml" file exists where the "VIRTUAL_ENV" is

        OR
        - The "UV_PROJECT_ENVIRONMENT" is equal to "VIRTUAL_ENV"

        If at least one of these conditions are not met,
        we are in a temporary virtual environment (e.g. `uvx marimo edit` or `uv --with=marimo run marimo edit`)
        or in the currently activated virtual environment (e.g. `uv venv`).
        """
        if not self._use_project:
            return False

        # Check we have a virtual environment
        venv_path = os.environ.get("VIRTUAL_ENV", None)
        if not venv_path:
            return False

        # Check that the "UV_PROJECT_ENVIRONMENT" is equal to "VIRTUAL_ENV"
        uv_project_environment = os.environ.get("UV_PROJECT_ENVIRONMENT", None)
        if uv_project_environment == venv_path:
            return True

        # Check that the `UV` environment variable is set
        # This tells us that marimo was run by uv
        uv_env_exists = os.environ.get("UV", None)
        if not uv_env_exists:
            return False
        # Check that the uv.lock and pyproject.toml files exist
        uv_lock_path = Path(venv_path).parent / "uv.lock"
        pyproject_path = Path(venv_path).parent / "pyproject.toml"
        return uv_lock_path.exists() and pyproject_path.exists()

    async def uninstall(self, package: str, group: str | None = None) -> bool:
        uninstall_cmd: list[str]
        if self.is_in_uv_project:
            LOGGER.info(f"Uninstalling {package} with 'uv remove'")
            uninstall_cmd = [self._uv_bin, "remove"]
            if group:
                uninstall_cmd.extend(["--group", group])
        else:
            LOGGER.info(f"Uninstalling {package} with 'uv pip uninstall'")
            uninstall_cmd = [self._uv_bin, "pip", "uninstall"]

        return await self.run(
            uninstall_cmd + [*split_packages(package), "-p", self._python_exe],
            log_callback=None,
        )

    def list_packages(self) -> list[PackageDescription]:
        # First try with `uv tree`
        tree = self.dependency_tree()
        if tree is not None:
            LOGGER.info("Listing packages with 'uv tree'")
            seen: set[str] = set()
            packages: list[PackageDescription] = []
            stack = list(tree.dependencies)
            while stack:
                pkg = stack.pop()
                if pkg.name not in seen:
                    packages.append(
                        PackageDescription(
                            name=pkg.name, version=pkg.version or ""
                        )
                    )
                    seen.add(pkg.name)
                    # Add dependencies to stack for recursion
                    stack.extend(pkg.dependencies)
            return sorted(packages, key=lambda pkg: pkg.name)

        LOGGER.info("Listing packages with 'uv pip list'")
        cmd = [
            self._uv_bin,
            "pip",
            "list",
            "--format=json",
            "-p",
            self._python_exe,
        ]
        return self._list_packages_from_cmd(cmd)

    def _has_script_metadata(self, filename: str) -> bool:
        """Check if a file contains PEP 723 inline script metadata."""
        try:
            file = Path(filename)
            return self.SCRIPT_METADATA_MARKER in file.read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeDecodeError):
            return False

    def dependency_tree(
        self, filename: str | None = None
    ) -> DependencyTreeNode | None:
        """Return the project's dependency tree using the `uv tree` command."""

        # Skip if not a script and not inside a uv-managed project
        if filename is None and not self.is_in_uv_project:
            return None

        tree_cmd = ["tree", "--no-dedupe"]
        if filename:
            tree_cmd += ["--script", filename]

        try:
            result = uv(tree_cmd)
            tree = parse_uv_tree(result.stdout)

            # If in a uv project and the only top-level item is the project itself,
            # return its dependencies directly
            if filename is None and len(tree.dependencies) == 1:
                return tree.dependencies[0]

            return tree

        except UvCommandError:
            # Only log error if the script has dependency metadata
            if filename and self._has_script_metadata(filename):
                LOGGER.error(f"Failed to get dependency tree for {filename}")
            return None


class RyePackageManager(PypiPackageManager):
    name = "rye"
    docs_url = "https://rye.astral.sh/"

    def install_command(
        self, package: str, *, upgrade: bool, group: str | None = None
    ) -> list[str]:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        return [
            "rye",
            *(["sync", "--update"] if upgrade else ["add"]),
            *split_packages(package),
        ]

    async def uninstall(self, package: str, group: str | None = None) -> bool:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        return await self.run(
            ["rye", "remove", *split_packages(package)], log_callback=None
        )

    def list_packages(self) -> list[PackageDescription]:
        cmd = ["rye", "list", "--format=json"]
        return self._list_packages_from_cmd(cmd)


class PoetryPackageManager(PypiPackageManager):
    name = "poetry"
    docs_url = "https://python-poetry.org/docs/"

    def _get_poetry_version(self) -> int:
        proc = run_package_command(
            ["poetry", "--version"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return -1  # and raise on the impl side
        version_str = proc.stdout.split()[-1].strip("()")
        major, *_ = map(int, version_str.split("."))
        return major

    def install_command(
        self, package: str, *, upgrade: bool, group: str | None = None
    ) -> list[str]:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        return [
            "poetry",
            "update" if upgrade else "add",
            "--no-interaction",
            *split_packages(package),
        ]

    async def uninstall(self, package: str, group: str | None = None) -> bool:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        return await self.run(
            ["poetry", "remove", "--no-interaction", *split_packages(package)],
            log_callback=None,
        )

    def _list_packages_from_cmd(
        self, cmd: list[str]
    ) -> list[PackageDescription]:
        if not self.is_manager_installed():
            return []

        proc = run_package_command(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            return []

        # Each line in package_lines is of the form
        # package_name    version_string      some more arbitrary text
        #
        # For each line, extract the package_name and version_string, ignoring
        # the rest of the text.
        package_lines = proc.stdout.splitlines()
        packages = []
        for line in package_lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            packages.append(
                PackageDescription(name=parts[0], version=parts[1])
            )
        return packages

    def _generate_list_packages_cmd(self, version: int) -> list[str]:
        """Poetry 1.x and 2.x handle the "show" command differently
        In poetry 1.x, "poetry show --no-dev" works perfectly fine but is deprecated. This
            shouldn't matter if 1.8.x is still installed.
        In poetry 2.x the preferred command is "poetry show --without dev" but will throw
            an error if there are no dev packages installed. We will capture that error and
            adjust the cmd accordingly.
        """
        if version == 1:
            return ["poetry", "show", "--no-dev"]

        elif version != 2:
            LOGGER.warning(
                f"Unknown poetry version {version}, attempting fallback"
            )

        try:
            cmd = ["poetry", "show", "--without", "dev"]
            result = run_package_command(
                cmd,
                capture_output=True,
                text=True,
            )

            # If Poetry 2.x throws "Group(s) not found"
            if "Group(s) not found" in result.stderr:
                return ["poetry", "show"]

            # Otherwise, if the command succeeded
            if result.returncode == 0:
                return cmd

        except FileNotFoundError:
            return []

        # Default fallback
        return ["poetry", "show"]

    def list_packages(self) -> list[PackageDescription]:
        version = self._get_poetry_version()
        cmd = self._generate_list_packages_cmd(version)
        return self._list_packages_from_cmd(cmd)
