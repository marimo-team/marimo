# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from marimo import _loggers
from marimo._cli.files.file_path import FileContentReader
from marimo._cli.print import echo
from marimo._utils.code import hash_code
from marimo._utils.paths import normalize_path
from marimo._utils.scripts import read_pyproject_from_script

if TYPE_CHECKING:
    from marimo._utils.marimo_path import MarimoPath

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

        if not (name.endswith((".md", ".qmd"))):
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
    """
    dependencies = cast(list[str], pyproject.get("dependencies", []))
    if not dependencies:
        return []

    uv_sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})

    for dependency, source in uv_sources.items():
        # Find the index of the dependency. This may have a version
        # attached, so we cannot do .index()
        dep_index: int | None = None
        for i, dep in enumerate(dependencies):
            if dep == dependency or dep.startswith(
                (
                    f"{dependency}==",
                    f"{dependency}<",
                    f"{dependency}>",
                    f"{dependency}~",
                )
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
                source_path = normalize_path(config_dir / source_path)
            new_dependency = f"{dependency} @ {source_path!s}"

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


def _normalize_pep503(name: str) -> str:
    """Normalize a project name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


# Captures the leading bare project name (with optional extras) of a PEP 508
# dependency string. Stops at the first version specifier, marker, or URL
# delimiter.
_DEP_NAME_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]+\])?)"
)


def _pin_dep(dep: str, pins: dict[str, str]) -> str:
    """Replace any version specifier in `dep` with the pinned version.

    Returns `dep` unchanged if the name doesn't appear in `pins`, or if the
    dependency uses a URL/VCS source (we don't override explicit URLs).
    """
    stripped = dep.strip()
    if (
        not stripped
        or "@" in stripped
        or stripped.startswith(("git+", "http"))
    ):
        return dep

    match = _DEP_NAME_RE.match(stripped)
    if match is None:
        return dep

    name_with_extras = match.group("name")
    bare_name = name_with_extras.split("[", 1)[0]
    canonical = _normalize_pep503(bare_name)
    if canonical not in pins:
        return dep

    rest = stripped[match.end() :]
    # Preserve any environment marker (`; python_version >= ...`).
    marker = ""
    if ";" in rest:
        _, _, marker_text = rest.partition(";")
        marker = f";{marker_text}"

    return f"{name_with_extras}=={pins[canonical]}{marker}"


def with_pinned_dependencies(
    code: str,
    pins: dict[str, str],
    *,
    lock_kind: str,
) -> str:
    """Rewrite the PEP 723 [run] dependencies block to pin top-level names.

    Args:
        code: Notebook source containing (optionally) a PEP 723 block.
        pins: Mapping of canonical (PEP 503) package name → version string.
        lock_kind: Annotation written to `[tool.marimo.export] lock_kind`,
            e.g. "resolved" or "observed".

    Names not in `pins` are left as-is. URL/VCS dependencies are not
    rewritten. If the script has no PEP 723 block, `code` is returned
    unchanged.
    """
    from marimo._utils.scripts import (
        REGEX,
        read_pyproject_from_script,
        write_pyproject_to_script,
    )

    project = read_pyproject_from_script(code)
    if project is None:
        return code

    deps = project.get("dependencies")
    if isinstance(deps, list):
        project["dependencies"] = [_pin_dep(str(dep), pins) for dep in deps]

    tool = project.setdefault("tool", {})
    if not isinstance(tool, dict):
        tool = {}
        project["tool"] = tool
    marimo_tool = tool.setdefault("marimo", {})
    if not isinstance(marimo_tool, dict):
        marimo_tool = {}
        tool["marimo"] = marimo_tool
    export_section = marimo_tool.setdefault("export", {})
    if not isinstance(export_section, dict):
        export_section = {}
        marimo_tool["export"] = export_section
    export_section["lock_kind"] = lock_kind

    new_block = write_pyproject_to_script(project)
    return re.sub(REGEX, new_block, code, count=1)


def pin_pep723_dependencies_for_wasm(code: str, path: MarimoPath) -> str:
    """Pin a notebook's PEP 723 deps for embedding in a WASM HTML export.

    For each top-level dep also shipped in the Pyodide lockfile, pin to the
    *lockfile* version — that's what micropip will install in the browser,
    so embedding any other pin would be a lie that breaks the export. If
    the lockfile fetch fails, degrade to pinning the locally installed
    version (best-effort; the WASM runtime falls back to its bundled
    lockfile). Also warns about top-level dependencies that aren't shipped
    in pyodide-lock — those may fail to install via micropip. The lock
    kind is "resolved" when we ran inside the html-wasm sandbox, otherwise
    "observed".
    """
    from importlib.metadata import distributions

    from marimo._pyodide.pyodide_constraints import (
        fetch_pyodide_package_versions,
        normalize_package_name,
    )

    installed: dict[str, str] = {}
    for dist in distributions():
        name = dist.metadata["Name"]
        version = dist.version
        if name and version:
            installed[normalize_package_name(name)] = version

    pyodide_versions: dict[str, str] = {}
    try:
        pyodide_versions = {
            normalize_package_name(n): v
            for n, v in fetch_pyodide_package_versions().items()
        }
        # Pin to lockfile versions for names the browser can actually
        # install. Restricting to installed names keeps the pin set small
        # and noise-free (an irrelevant pin for an unused dep is harmless
        # but unnecessary churn).
        pins = {
            name: pyodide_versions[name]
            for name in installed
            if name in pyodide_versions
        }
    except Exception:
        # Fetch failures degrade to pinning whatever is installed; the
        # WASM micropip will still try its bundled lockfile first.
        pins = installed
    pyodide_names = set(pyodide_versions)

    # Warn about top-level deps not bundled in pyodide. micropip *may*
    # still install pure-python ones from PyPI in the browser; native
    # ones (jax, torch, numpy alternatives) will fail. We don't know
    # which from here, so emit a single advisory.
    if pyodide_names:
        try:
            pyproject = PyProjectReader.from_filename(path.absolute_name)
            top_level: list[str] = []
            for dep in pyproject.dependencies:
                match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", dep.strip())
                if match is None:
                    continue
                canonical = normalize_package_name(match.group(1))
                if canonical == "marimo" or canonical in pyodide_names:
                    continue
                top_level.append(match.group(1))
            if top_level:
                echo(
                    "warn: these dependencies are not bundled in the "
                    "Pyodide lockfile and may fail to install in the "
                    "browser: " + ", ".join(sorted(set(top_level))),
                    err=True,
                )
        except Exception as e:
            LOGGER.debug("Skipped wasm compat warn: %s", e)

    lock_kind = (
        "resolved"
        if os.environ.get("MARIMO_HTML_WASM_SANDBOX_BOOTSTRAPPED") == "1"
        else "observed"
    )
    return with_pinned_dependencies(code, pins, lock_kind=lock_kind)


def get_headers_from_markdown(contents: str) -> dict[str, str]:
    from marimo._convert.markdown.to_ir import extract_frontmatter

    frontmatter, _ = extract_frontmatter(contents)
    return get_headers_from_frontmatter(frontmatter)


def get_headers_from_frontmatter(
    frontmatter: dict[str, Any],
) -> dict[str, str]:
    from marimo._utils.scripts import wrap_script_metadata

    headers = {"pyproject": "", "header": ""}

    pyproject = frontmatter.get("pyproject", "")
    if pyproject:
        if not pyproject.startswith("#"):
            # Wrap raw TOML content in PEP 723 format
            pyproject = wrap_script_metadata(pyproject)
        headers["pyproject"] = pyproject
    headers["header"] = frontmatter.get("header", "")
    return headers


def has_marimo_in_script_metadata(filepath: str) -> bool | None:
    """Check if marimo is in the file's PEP 723 script metadata dependencies.

    Returns:
        True if marimo is in dependencies
        False if script metadata exists but marimo is not in dependencies
        None if file has no script metadata
    """

    project = _get_pyproject_from_filename(filepath)
    if project is None:
        return None

    dependencies = project.get("dependencies", [])
    return any(is_marimo_dependency(dep) for dep in dependencies)


def script_metadata_hash_from_filename(name: str) -> str | None:
    project = _get_pyproject_from_filename(name)
    if project is None:
        return None
    serialized = json.dumps(
        project,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hash_code(serialized)
