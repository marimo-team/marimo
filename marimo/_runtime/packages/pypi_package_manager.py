# Copyright 2024 Marimo. All rights reserved.
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
    PackageDescription,
)
from marimo._runtime.packages.utils import split_packages
from marimo._utils.platform import is_pyodide

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
        proc = subprocess.run(cmd, capture_output=True, text=True)
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

    async def _install(self, package: str) -> bool:
        LOGGER.info(f"Installing {package} with pip")
        return self.run(
            ["pip", "--python", PY_EXE, "install", *split_packages(package)]
        )

    async def uninstall(self, package: str) -> bool:
        LOGGER.info(f"Uninstalling {package} with pip")
        return self.run(
            [
                "pip",
                "--python",
                PY_EXE,
                "uninstall",
                "-y",
                *split_packages(package),
            ]
        )

    def list_packages(self) -> list[PackageDescription]:
        cmd = ["pip", "--python", PY_EXE, "list", "--format=json"]
        return self._list_packages_from_cmd(cmd)


class MicropipPackageManager(PypiPackageManager):
    name = "micropip"
    docs_url = "https://micropip.pyodide.org/"

    def should_auto_install(self) -> bool:
        return True

    def is_manager_installed(self) -> bool:
        return is_pyodide()

    async def _install(self, package: str) -> bool:
        assert is_pyodide()
        import micropip  # type: ignore

        try:
            await micropip.install(split_packages(package))
            return True
        except ValueError:
            return False

    async def uninstall(self, package: str) -> bool:
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

    async def _install(self, package: str) -> bool:
        install_cmd: list[str]
        if self.is_in_uv_project:
            LOGGER.info(f"Installing in {package} with 'uv add'")
            install_cmd = ["uv", "add"]
        else:
            LOGGER.info(f"Installing in {package} with 'uv pip install'")
            install_cmd = ["uv", "pip", "install"]

        return self.run(
            # trade installation time for faster start time
            install_cmd + ["--compile", *split_packages(package), "-p", PY_EXE]
        )

    def update_notebook_script_metadata(
        self,
        filepath: str,
        *,
        packages_to_add: Optional[list[str]] = None,
        packages_to_remove: Optional[list[str]] = None,
        import_namespaces_to_add: Optional[list[str]] = None,
        import_namespaces_to_remove: Optional[list[str]] = None,
    ) -> None:
        """Update the notebook's script metadata with the packages to add/remove.

        Args:
            filepath: Path to the notebook file
            packages_to_add: List of packages to add to the script metadata
            packages_to_remove: List of packages to remove from the script metadata
            import_namespaces_to_add: List of import namespaces to add
            import_namespaces_to_remove: List of import namespaces to remove
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
            return

        LOGGER.info(f"Updating script metadata for {filepath}")

        version_map = self._get_version_map()

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

        # Filter to packages that are found in "uv pip list"
        packages_to_add = [
            _maybe_add_version(im)
            for im in packages_to_add
            if _is_installed(im)
        ]

        if filepath.endswith(".md") or filepath.endswith(".qmd"):
            # md and qmd require writing to a faux python file first.
            return self._process_md_changes(
                filepath, packages_to_add, packages_to_remove
            )
        return self._process_changes_for_script_metadata(
            filepath, packages_to_add, packages_to_remove
        )

    def _process_md_changes(
        self,
        filepath: str,
        packages_to_add: list[str],
        packages_to_remove: list[str],
    ) -> None:
        from marimo._cli.convert.markdown import extract_frontmatter
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
        self._process_changes_for_script_metadata(
            temp_file.name,
            packages_to_add,
            packages_to_remove,
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

    def _process_changes_for_script_metadata(
        self,
        filepath: str,
        packages_to_add: list[str],
        packages_to_remove: list[str],
    ) -> None:
        if packages_to_add:
            self.run(
                ["uv", "--quiet", "add", "--script", filepath]
                + packages_to_add
            )
        if packages_to_remove:
            self.run(
                ["uv", "--quiet", "remove", "--script", filepath]
                + packages_to_remove
            )

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

        If at least one of these conditions are not met,
        we are in a temporary virtual environment (e.g. `uvx marimo edit` or `uv --with=marimo run marimo edit`)
        or in the currently activated virtual environment (e.g. `uv venv`).
        """
        # Check we have a virtual environment
        venv_path = os.environ.get("VIRTUAL_ENV", None)
        if not venv_path:
            return False
        # Check that the `UV` environment variable is set
        # This tells us that marimo was run by uv
        uv_env_exists = os.environ.get("UV", None)
        if not uv_env_exists:
            return False
        # Check that the uv.lock and pyproject.toml files exist
        uv_lock_path = Path(venv_path).parent / "uv.lock"
        pyproject_path = Path(venv_path).parent / "pyproject.toml"
        return uv_lock_path.exists() and pyproject_path.exists()

    async def uninstall(self, package: str) -> bool:
        uninstall_cmd: list[str]
        if self.is_in_uv_project:
            LOGGER.info(f"Uninstalling {package} with 'uv remove'")
            uninstall_cmd = ["uv", "remove"]
        else:
            LOGGER.info(f"Uninstalling {package} with 'uv pip uninstall'")
            uninstall_cmd = ["uv", "pip", "uninstall"]

        return self.run(
            uninstall_cmd + [*split_packages(package), "-p", PY_EXE]
        )

    def list_packages(self) -> list[PackageDescription]:
        LOGGER.info("Listing packages with 'uv pip list'")
        cmd = ["uv", "pip", "list", "--format=json", "-p", PY_EXE]
        return self._list_packages_from_cmd(cmd)


class RyePackageManager(PypiPackageManager):
    name = "rye"
    docs_url = "https://rye.astral.sh/"

    async def _install(self, package: str) -> bool:
        return self.run(["rye", "add", *split_packages(package)])

    async def uninstall(self, package: str) -> bool:
        return self.run(["rye", "remove", *split_packages(package)])

    def list_packages(self) -> list[PackageDescription]:
        cmd = ["rye", "list", "--format=json"]
        return self._list_packages_from_cmd(cmd)


class PoetryPackageManager(PypiPackageManager):
    name = "poetry"
    docs_url = "https://python-poetry.org/docs/"

    async def _install(self, package: str) -> bool:
        return self.run(
            ["poetry", "add", "--no-interaction", *split_packages(package)]
        )

    async def uninstall(self, package: str) -> bool:
        return self.run(
            ["poetry", "remove", "--no-interaction", *split_packages(package)]
        )

    def _list_packages_from_cmd(
        self, cmd: list[str]
    ) -> list[PackageDescription]:
        if not self.is_manager_installed():
            return []
        proc = subprocess.run(cmd, capture_output=True, text=True)
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

    def list_packages(self) -> list[PackageDescription]:
        cmd = ["poetry", "show", "--no-dev"]
        return self._list_packages_from_cmd(cmd)
