# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from functools import cached_property
from pathlib import Path
from typing import Optional

from marimo import _loggers
from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)
from marimo._runtime.packages.package_manager import (
    CanonicalizingPackageManager,
    LogCallback,
    PackageDescription,
)
from marimo._runtime.packages.utils import split_packages
from marimo._utils.platform import is_pyodide
from marimo._utils.uv import find_uv_bin
from marimo._utils.uv_tree import DependencyTreeNode, parse_uv_tree

PY_EXE = sys.executable

LOGGER = _loggers.marimo_logger()


class PypiPackageManager(CanonicalizingPackageManager):
    def _construct_module_name_mapping(self) -> dict[str, str]:
        return module_name_to_pypi_name()

    def _list_packages_from_cmd(
        self, cmd: list[str]
    ) -> list[PackageDescription]:
        if not self.is_manager_installed():
            return []
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8"
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

    def install_command(
        self, package: str, *, upgrade: bool, dev: bool
    ) -> list[str]:
        # The `dev` parameter is accepted for interface compatibility, but is ignored.
        del dev
        return [
            "pip",
            "--python",
            PY_EXE,
            "install",
            *(["--upgrade"] if upgrade else []),
            *split_packages(package),
        ]

    async def uninstall(self, package: str, dev: bool) -> bool:
        # The `dev` parameter is accepted for interface compatibility, but is ignored.
        del dev
        LOGGER.info(f"Uninstalling {package} with pip")
        return await self.run(
            [
                "pip",
                "--python",
                PY_EXE,
                "uninstall",
                "-y",
                *split_packages(package),
            ],
            log_callback=None,
        )

    def list_packages(self) -> list[PackageDescription]:
        cmd = ["pip", "--python", PY_EXE, "list", "--format=json"]
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
        dev: bool,
        log_callback: Optional[LogCallback] = None,
    ) -> bool:
        # The `dev` parameter is accepted for interface compatibility, but is ignored.
        del dev
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

    async def uninstall(self, package: str, dev: bool) -> bool:
        # The `dev` parameter is accepted for interface compatibility, but is ignored.
        del dev
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
        self, package: str, *, upgrade: bool, dev: bool = False
    ) -> list[str]:
        install_cmd: list[str]
        if self.is_in_uv_project:
            install_cmd = [self._uv_bin, "add"]
            if dev:
                install_cmd.append("--dev")
        else:
            install_cmd = [self._uv_bin, "pip", "install"]

            # Allow for explicit site directory location if needed
            target = os.environ.get("MARIMO_UV_TARGET", None)
            if target:
                install_cmd.append(f"--target={target}")

        if upgrade:
            install_cmd.append("--upgrade")

        return install_cmd + [
            # trade installation time for faster start time
            "--compile",
            *split_packages(package),
            "-p",
            PY_EXE,
        ]

    async def _install(
        self,
        package: str,
        *,
        upgrade: bool,
        dev: bool,
        log_callback: Optional[LogCallback] = None,
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
                dev=dev,
                log_callback=log_callback,
            )

        # For uv pip install, try with output capture to enable fallback
        cmd = self.install_command(package, upgrade=upgrade, dev=dev)

        # Run the command and capture output
        proc = subprocess.Popen(  # noqa: ASYNC220
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=False,
            bufsize=0,
        )

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

            # Retry with --no-cache flag
            cmd_with_no_cache = cmd + ["--no-cache"]
            return await self.run(cmd_with_no_cache, log_callback=log_callback)

        return False

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
            if package.startswith("git+") or package.startswith("git://"):
                return True
            # Direct references with @ (PEP 440 direct references)
            if " @ " in package:
                return True
            # URLs (https://, http://, file://)
            if "://" in package:
                return True
            return False

        def _is_installed(package: str) -> bool:
            without_brackets = package.split("[")[0]
            return without_brackets.lower() in version_map

        def _maybe_add_version(package: str) -> str:
            # Skip marimo and marimo[<mod>], but not marimo-<something-else>
            if package == "marimo" or package.startswith("marimo["):
                return package
            without_brackets = package.split("[")[0]
            version = version_map.get(without_brackets.lower())
            if version:
                return f"{package}=={version}"
            return package

        # Filter to packages that are found in "uv pip list" OR are direct references
        # Direct references (git URLs, direct URLs, local paths) bypass the installed check
        # because they won't appear in the version map with their full reference syntax
        packages_to_add = [
            _maybe_add_version(im) if not _is_direct_reference(im) else im
            for im in packages_to_add
            if _is_direct_reference(im) or _is_installed(im)
        ]

        if filepath.endswith(".md") or filepath.endswith(".qmd"):
            # md and qmd require writing to a faux python file first.
            return self._process_md_changes(
                filepath, packages_to_add, packages_to_remove, upgrade=upgrade
            )
        return self._process_changes_for_script_metadata(
            filepath, packages_to_add, packages_to_remove, upgrade=upgrade
        )

    def _process_md_changes(
        self,
        filepath: str,
        packages_to_add: list[str],
        packages_to_remove: list[str],
        upgrade: bool,
    ) -> bool:
        from marimo._convert.markdown.markdown import extract_frontmatter
        from marimo._utils import yaml
        from marimo._utils.inline_script_metadata import (
            get_headers_from_frontmatter,
        )

        # Get script metadata
        with open(filepath, encoding="utf-8") as f:
            frontmatter, body = extract_frontmatter(f.read())
        headers = get_headers_from_frontmatter(frontmatter)
        pyproject = bool(headers.get("pyproject", ""))
        header = (
            headers.get("pyproject", "")
            if pyproject
            else headers.get("header", "")
        )
        pyproject = pyproject or not bool(header)

        # Write out and process the header
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".py", encoding="utf-8"
        ) as temp_file:
            temp_file.write(header)
            temp_file.flush()
        # Have UV modify it
        result = self._process_changes_for_script_metadata(
            temp_file.name,
            packages_to_add,
            packages_to_remove,
            upgrade=upgrade,
        )
        with open(temp_file.name, encoding="utf-8") as f:
            header = f.read()
        # Clean up the temporary file
        os.unlink(temp_file.name)

        # Write back the changes to the original file
        if pyproject:
            # Strip '# '
            # and leading/trailing ///
            header = "\n".join(
                [line[2:] for line in header.strip().splitlines()[1:-1]]
            )
            frontmatter["pyproject"] = header
        else:
            frontmatter["header"] = header

        header = yaml.marimo_compat_dump(
            frontmatter,
            sort_keys=False,
        )
        document = ["---", header.strip(), "---", body]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(document))

        return result

    def _process_changes_for_script_metadata(
        self,
        filepath: str,
        packages_to_add: list[str],
        packages_to_remove: list[str],
        upgrade: bool,
    ) -> bool:
        success = True
        if packages_to_add:
            cmd = [self._uv_bin, "--quiet", "add", "--script", filepath]
            if upgrade:
                cmd.append("--upgrade")
            cmd.extend(packages_to_add)
            success &= self._run_sync(cmd, log_callback=None)
        if packages_to_remove:
            success &= self._run_sync(
                [self._uv_bin, "--quiet", "remove", "--script", filepath]
                + packages_to_remove,
                log_callback=None,
            )
        return success

    def _get_version_map(self) -> dict[str, str]:
        packages = self.list_packages()
        return {pkg.name: pkg.version for pkg in packages}

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

    async def uninstall(self, package: str, dev: bool = False) -> bool:
        uninstall_cmd: list[str]
        if self.is_in_uv_project:
            LOGGER.info(f"Uninstalling {package} with 'uv remove'")
            uninstall_cmd = [self._uv_bin, "remove"]
            if dev:
                uninstall_cmd.append("--dev")
        else:
            LOGGER.info(f"Uninstalling {package} with 'uv pip uninstall'")
            uninstall_cmd = [self._uv_bin, "pip", "uninstall"]

        return await self.run(
            uninstall_cmd + [*split_packages(package), "-p", PY_EXE],
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
        cmd = [self._uv_bin, "pip", "list", "--format=json", "-p", PY_EXE]
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
        self, filename: Optional[str] = None
    ) -> Optional[DependencyTreeNode]:
        """Return the project's dependency tree using the `uv tree` command."""

        # Skip if not a script and not inside a uv-managed project
        if filename is None and not self.is_in_uv_project:
            return None

        tree_cmd = [self._uv_bin, "tree", "--no-dedupe"]
        if filename:
            tree_cmd += ["--script", filename]

        try:
            result = subprocess.run(
                tree_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            tree = parse_uv_tree(result.stdout)

            # If in a uv project and the only top-level item is the project itself,
            # return its dependencies directly
            if filename is None and len(tree.dependencies) == 1:
                return tree.dependencies[0]

            return tree

        except subprocess.CalledProcessError:
            # Only log error if the script has dependency metadata
            if filename and self._has_script_metadata(filename):
                LOGGER.error(f"Failed to get dependency tree for {filename}")
            return None


class RyePackageManager(PypiPackageManager):
    name = "rye"
    docs_url = "https://rye.astral.sh/"

    def install_command(
        self, package: str, *, upgrade: bool, dev: bool
    ) -> list[str]:
        # The `dev` parameter is accepted for interface compatibility, but is ignored.
        del dev
        return [
            "rye",
            *(["sync", "--update"] if upgrade else ["add"]),
            *split_packages(package),
        ]

    async def uninstall(self, package: str, dev: bool) -> bool:
        # The `dev` parameter is accepted for interface compatibility, but is ignored.
        del dev
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
        proc = subprocess.run(
            ["poetry", "--version"], capture_output=True, text=True
        )
        if proc.returncode != 0:
            return -1  # and raise on the impl side
        version_str = proc.stdout.split()[-1].strip("()")
        major, *_ = map(int, version_str.split("."))
        return major

    def install_command(
        self, package: str, *, upgrade: bool, dev: bool
    ) -> list[str]:
        # The `dev` parameter is accepted for interface compatibility, but is ignored.
        del dev
        return [
            "poetry",
            "update" if upgrade else "add",
            "--no-interaction",
            *split_packages(package),
        ]

    async def uninstall(self, package: str, dev: bool) -> bool:
        # The `dev` parameter is accepted for interface compatibility, but is ignored.
        del dev
        return await self.run(
            ["poetry", "remove", "--no-interaction", *split_packages(package)],
            log_callback=None,
        )

    def _list_packages_from_cmd(
        self, cmd: list[str]
    ) -> list[PackageDescription]:
        if not self.is_manager_installed():
            return []

        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8"
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
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False
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
