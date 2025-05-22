# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from marimo import _loggers
from marimo._cli.file_path import FileContentReader
from marimo._utils.scripts import read_pyproject_from_script

LOGGER = _loggers.marimo_logger()


class PyProjectReader:
    def __init__(
        self,
        project: dict[str, Any],
        *,
        config_path: str | None,
        name: str | None = None,
    ):
        self.project = project
        self.config_path = config_path
        self.name = name

    @staticmethod
    def from_filename(name: str) -> PyProjectReader:
        return PyProjectReader(
            name=name,
            project=_get_pyproject_from_filename(name) or {},
            config_path=name,
        )

    @staticmethod
    def from_script(script: str) -> PyProjectReader:
        return PyProjectReader(
            project=read_pyproject_from_script(script) or {},
            config_path=None,
            name=None,
        )

    @property
    def extra_index_urls(self) -> list[str]:
        # See https://docs.astral.sh/uv/reference/settings/#pip_extra-index-url
        return (  # type: ignore[no-any-return]
            self.project.get("tool", {})
            .get("uv", {})
            .get("extra-index-url", [])
        )

    @property
    def index_configs(self) -> list[dict[str, str]]:
        # See https://docs.astral.sh/uv/reference/settings/#index
        return self.project.get("tool", {}).get("uv", {}).get("index", [])  # type: ignore[no-any-return]

    @property
    def index_url(self) -> str | None:
        # See https://docs.astral.sh/uv/reference/settings/#pip_index-url
        return (  # type: ignore[no-any-return]
            self.project.get("tool", {}).get("uv", {}).get("index-url", None)
        )

    @property
    def python_version(self) -> str | None:
        try:
            version = self.project.get("requires-python")
            # Only return string version requirements
            if not isinstance(version, str):
                return None
            return version
        except Exception as e:
            LOGGER.warning(f"Failed to parse Python version requirement: {e}")
            return None

    @property
    def dependencies(self) -> list[str]:
        return self.project.get("dependencies", [])  # type: ignore[no-any-return]

    @property
    def requirements_txt_lines(self) -> list[str]:
        """Get dependencies from string representation of script."""
        try:
            return _pyproject_toml_to_requirements_txt(
                self.project, self.config_path
            )
        except Exception as e:
            LOGGER.warning(f"Failed to parse dependencies: {e}")
            return []


def _get_pyproject_from_filename(name: str) -> dict[str, Any] | None:
    try:
        contents, _ = FileContentReader().read_file(name)
        if name.endswith(".py"):
            return read_pyproject_from_script(contents)

        if not (name.endswith(".md") or name.endswith(".qmd")):
            raise ValueError(
                f"Unsupported file type: {name}. Only .py and .md files are supported."
            )

        headers = get_headers_from_markdown(contents)
        header = headers["pyproject"]
        if not header:
            header = headers["header"]
        elif headers["header"]:
            pyproject = PyProjectReader.from_script(headers["header"])
            if pyproject.dependencies or pyproject.python_version:
                LOGGER.warning(
                    "Both header and pyproject provide dependencies. "
                    "Preferring pyproject."
                )
        return read_pyproject_from_script(header)
    except FileNotFoundError:
        return None
    except Exception:
        LOGGER.warning(f"Failed to read pyproject.toml from {name}")
        return None


def _pyproject_toml_to_requirements_txt(
    pyproject: dict[str, Any],
    config_path: str | None = None,
) -> list[str]:
    """
    Convert a pyproject.toml file to a requirements.txt file.

    If there is a `[tool.uv.sources]` section, we resolve the dependencies
    to their corresponding source.

    # dependencies = [
    #     "python-gcode",
    # ]
    #
    # [tool.uv.sources]
    # python-gcode = { git = "https://github.com/fetlab/python_gcode", rev = "new" }

    Args:
        pyproject: A dict containing the pyproject.toml contents.
        config_path: The path to the pyproject.toml or inline script metadata. This
            is used to resolve relative paths used in the dependencies.
    """  # noqa: E501
    dependencies = cast(list[str], pyproject.get("dependencies", []))
    if not dependencies:
        return []

    uv_sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})

    for dependency, source in uv_sources.items():
        # Find the index of the dependency. This may have a version
        # attached, so we cannot do .index()
        dep_index: int | None = None
        for i, dep in enumerate(dependencies):
            if (
                dep == dependency
                or dep.startswith(f"{dependency}==")
                or dep.startswith(f"{dependency}<")
                or dep.startswith(f"{dependency}>")
                or dep.startswith(f"{dependency}~")
            ):
                dep_index = i
                break

        if dep_index is None:
            continue

        new_dependency = None

        # Handle git dependencies
        if "git" in source:
            git_url = f"git+{source['git']}"
            ref = (
                source.get("rev") or source.get("branch") or source.get("tag")
            )
            new_dependency = (
                f"{dependency} @ {git_url}@{ref}"
                if ref
                else f"{dependency} @ {git_url}"
            )
        # Handle local paths
        elif "path" in source:
            source_path = Path(source["path"])
            # If path is relative and we have a config path, resolve it relative to the config path
            if not source_path.is_absolute() and config_path:
                config_dir = Path(config_path).parent
                source_path = (config_dir / source_path).resolve()
            new_dependency = f"{dependency} @ {str(source_path)}"

        # Handle URLs
        elif "url" in source:
            new_dependency = f"{dependency} @ {source['url']}"

        if new_dependency:
            if source.get("marker"):
                new_dependency += f"; {source['marker']}"

            dependencies[dep_index] = new_dependency

    return dependencies


def is_marimo_dependency(dependency: str) -> bool:
    # Split on any version specifier
    without_version = re.split(r"[=<>~]+", dependency)[0]
    # Match marimo and marimo[extras], but not marimo-<something-else>
    return without_version == "marimo" or without_version.startswith("marimo[")


def get_headers_from_markdown(contents: str) -> dict[str, str]:
    from marimo._cli.convert.markdown import extract_frontmatter

    frontmatter, _ = extract_frontmatter(contents)
    return get_headers_from_frontmatter(frontmatter)


def get_headers_from_frontmatter(
    frontmatter: dict[str, Any],
) -> dict[str, str]:
    headers = {"pyproject": "", "header": ""}

    pyproject = frontmatter.get("pyproject", "")
    if pyproject:
        if not pyproject.startswith("#"):
            pyproject = "\n# ".join(
                [r"# /// script", *pyproject.splitlines(), r"///"]
            )
        headers["pyproject"] = pyproject
    headers["header"] = frontmatter.get("header", "")
    return headers
