# Copyright 2026 Marimo. All rights reserved.
"""The PEP 723 inline script metadata block.

This module is the single reader and writer for the `# /// script` block in
marimo notebooks. In-place edits of a user's file delegate to
`uv ... --script` so uv owns the TOML edit and the user's formatting
survives; whole-block generation (converters, codegen, export) serializes
with tomlkit.

Markdown notebooks (.md/.qmd) carry the block in their frontmatter; edit
verbs round-trip the header verbatim through a carrier, a hidden sidecar
next to the notebook, so uv anchors relative paths in the metadata
against the notebook's directory. uv also runs from that directory, so
directory-scoped uv configuration applies.
"""

from __future__ import annotations

import contextlib
import os
import platform
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._environments.errors import EnvironmentManagerError
from marimo._environments.uv import (
    UvError,
    script_command_env,
    uv,
    uv_stream,
)
from marimo._utils.toml import toml_reader

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

LOGGER = _loggers.marimo_logger()

REGEX = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


class ScriptMetadataError(EnvironmentManagerError):
    """A script metadata edit could not be completed."""


def loads(script: str) -> dict[str, Any] | None:
    """Parse the `# /// script` block, or None if the script has none.

    Adapted from https://peps.python.org/pep-0723/#reference-implementation
    """
    name = "script"
    matches = list(
        filter(lambda m: m.group("type") == name, re.finditer(REGEX, script))
    )
    if len(matches) > 1:
        raise ValueError(f"Multiple {name} blocks found")
    elif len(matches) == 1:
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in matches[0].group("content").splitlines(keepends=True)
        )
        return toml_reader.reads(content)
    else:
        return None


def dumps(project: dict[str, Any]) -> str:
    """Serialize a project dict to a `# /// script` block."""
    import tomlkit

    return wrap_block(tomlkit.dumps(project))


def wrap_block(toml_content: str) -> str:
    """Wrap raw TOML content in `# /// script` markers."""
    result_lines = ["# /// script"]
    for line in toml_content.rstrip().split("\n"):
        result_lines.append(f"# {line}")
    result_lines.append("# ///")
    return "\n".join(result_lines)


def replace_block(script: str, block: str) -> str:
    """Replace the script's existing `# /// script` block with `block`."""
    # A callable replacement keeps backslashes in `block` literal.
    return re.sub(REGEX, lambda _: block, script, count=1)


def with_python_version_requirement(project: dict[str, Any]) -> dict[str, Any]:
    # TODO(akshayka): consider locking the Python version for greater
    # reproducibility, instead of returning a lowerbound
    project = project.copy()
    version_tuple = platform.python_version_tuple()
    project["requires-python"] = f">={version_tuple[0]}.{version_tuple[1]}"
    return project


def add_dependencies(
    path: str,
    packages: Sequence[str],
    *,
    upgrade: bool = False,
    on_output: Callable[[str], None] | None = None,
) -> None:
    """Add packages to the script's metadata via `uv add --script`."""
    if not packages:
        return
    args = ["add", "--script"]

    def edit(target: str, cwd: str) -> None:
        command = [
            *args,
            target,
            *(["--upgrade"] if upgrade else []),
            *packages,
        ]
        if on_output is not None:
            uv_stream(command, on_output, env=script_command_env(), cwd=cwd)
        else:
            uv(["--quiet", *command], env=script_command_env(), cwd=cwd)

    _edit(path, edit)


def remove_dependencies(
    path: str,
    packages: Sequence[str],
    *,
    on_output: Callable[[str], None] | None = None,
) -> None:
    """Remove packages from the script's metadata via `uv remove --script`."""
    if not packages:
        return

    def edit(target: str, cwd: str) -> None:
        command = ["remove", "--script", target, *packages]
        if on_output is not None:
            uv_stream(command, on_output, env=script_command_env(), cwd=cwd)
        else:
            uv(["--quiet", *command], env=script_command_env(), cwd=cwd)

    _edit(path, edit)


def ensure_marimo(path: str) -> None:
    """Add marimo to the script metadata if it is not already a dependency.

    Creates the metadata block if the file has none. No-op for non-`.py`
    targets and for missing or empty files, whose block is the notebook
    serializer's to create.
    """
    if not path.endswith(".py"):
        return
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return

    from marimo._utils.inline_script_metadata import (
        has_marimo_in_script_metadata,
    )

    if has_marimo_in_script_metadata(path) is True:
        return

    def edit(target: str, cwd: str) -> None:
        uv(
            ["add", "--script", target, "marimo"],
            env=script_command_env(),
            timeout=30,
            cwd=cwd,
        )

    _edit(path, edit)


def ensure_requires_python(path: str) -> None:
    """Add `requires-python` to existing script metadata if not present.

    Splices the line directly after the opening marker instead of
    re-serializing, to avoid reformatting the user's block. No-op if the
    file has no metadata block.
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()

    project = loads(content)
    if project is None or "requires-python" in project:
        return

    version_tuple = platform.python_version_tuple()
    requires_line = (
        f'# requires-python = ">={version_tuple[0]}.{version_tuple[1]}"'
    )
    new_content = re.sub(
        r"^# /// script$",
        f"# /// script\n{requires_line}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)


def _edit(path: str, edit: Callable[[str, str], None]) -> None:
    """Apply an edit and normalize expected operational failures.

    Edits receive the file uv operates on and the working directory for
    the uv invocation, which is always the notebook's own directory so
    that directory-scoped uv configuration is discovered.
    """
    try:
        if path.endswith((".md", ".qmd")):
            _edit_frontmatter(path, edit)
        else:
            # uv resolves a relative --script target against the cwd this
            # module pins, so hand it an absolute path.
            absolute = os.path.abspath(path)
            edit(absolute, os.path.dirname(absolute))
    except (UvError, subprocess.TimeoutExpired, OSError) as error:
        raise ScriptMetadataError(
            f"Failed to update script metadata for {path}: {error}"
        ) from error


@dataclass(frozen=True)
class _Frontmatter:
    """A markdown notebook's frontmatter and its metadata block."""

    data: dict[str, Any]
    body: str
    # The comment-wrapped `# /// script` block.
    header: str
    # Whether the block came from the `pyproject` frontmatter key.
    is_pyproject: bool


def _read_frontmatter(path: str) -> _Frontmatter:
    from marimo._convert.markdown.to_ir import extract_frontmatter
    from marimo._utils.inline_script_metadata import (
        get_headers_from_frontmatter,
    )

    with open(path, encoding="utf-8") as f:
        data, body = extract_frontmatter(f.read())
    headers = get_headers_from_frontmatter(data)
    is_pyproject = bool(headers.get("pyproject", ""))
    header = (
        headers.get("pyproject", "")
        if is_pyproject
        else headers.get("header", "")
    )
    return _Frontmatter(
        data=data,
        body=body,
        header=header,
        is_pyproject=is_pyproject or not bool(header),
    )


# Bumping the version orphans every older carrier; `_sweep_carriers`
# recognizes and removes all versions.
_CARRIER_VERSION = 1


def _carrier_prefix(path: str) -> str:
    """The ownership-signed carrier prefix for a notebook.

    Deterministic per notebook filename, so a carrier is recognizably
    marimo's: safe to overwrite, sweep, and ignore.
    """
    return f".marimo-v{_CARRIER_VERSION}-{os.path.basename(path)}"


# A carrier lives for one uv command; a stray this old is stranded.
_SWEEP_AGE_SECONDS = 15 * 60


def _sweep_carriers(directory: str, path: str) -> None:
    """Removes stranded carriers for the notebook, best effort.

    Carriers are deleted after use; a killed process can strand one.
    Only strays older than `_SWEEP_AGE_SECONDS` are removed, sparing a
    concurrent process's in-flight carrier.
    """
    import time

    pattern = f".marimo-v*-{os.path.basename(path)}*.py"
    cutoff = time.time() - _SWEEP_AGE_SECONDS
    for stray in Path(directory).glob(pattern):
        try:
            if stray.stat().st_mtime < cutoff:
                stray.unlink()
        except OSError:
            LOGGER.debug("Could not remove carrier %s", stray)


@contextlib.contextmanager
def _carrier(
    notebook: str, content: str, *, stable: bool = False
) -> Iterator[str]:
    """A sidecar script uv can operate on, next to the notebook.

    uv anchors relative paths in script metadata to the script's own
    directory and keys a script environment on the script's absolute
    path, so a manifest that lives in frontmatter must be materialized
    beside its notebook before uv can act on it. The versioned,
    deterministic name (`.marimo-v<N>-<name>[.<rand>].py`) marks the
    file as marimo's: safe to overwrite, sweep, and ignore. A stable
    carrier maps one notebook to one environment across sessions; a
    unique one keeps concurrent edits apart. Entry sweeps carriers
    stranded by killed processes; exit always removes the carrier, best
    effort.
    """
    absolute = os.path.abspath(notebook)
    directory = os.path.dirname(absolute)
    _sweep_carriers(directory, absolute)
    try:
        if stable:
            target = os.path.join(directory, f"{_carrier_prefix(absolute)}.py")
            descriptor = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
            )
        else:
            descriptor, target = tempfile.mkstemp(
                dir=directory,
                prefix=f"{_carrier_prefix(absolute)}.",
                suffix=".py",
            )
    except OSError:
        # A read-only notebook directory cannot hold the carrier. Fall
        # back to a deterministic path in the temp directory; the
        # environment stays stable, but relative paths in the metadata
        # and directory-scoped uv configuration no longer resolve
        # against the notebook's directory.
        target = _fallback_carrier_path(absolute)
        LOGGER.warning(
            "Notebook directory is not writable; materializing the "
            "manifest at %s",
            target,
        )
        descriptor = os.open(
            target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
        )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            f.write(content)
        yield target
    finally:
        try:
            os.unlink(target)
        except OSError:
            LOGGER.debug("Could not remove carrier %s", target)


def _fallback_carrier_path(absolute: str) -> str:
    """A deterministic carrier path outside the notebook's directory.

    uv keys a script environment on the script's absolute path, so the
    fallback must be a pure function of the notebook's path.
    """
    import hashlib

    digest = hashlib.sha256(absolute.encode("utf-8")).hexdigest()[:16]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(absolute).stem)[:64]
    return os.path.join(
        tempfile.gettempdir(), f".marimo-v1-{stem}-{digest}.py"
    )


def _edit_frontmatter(path: str, edit: Callable[[str, str], None]) -> None:
    """Edits metadata carried in markdown frontmatter.

    The header is materialized verbatim as a carrier next to the
    notebook, so uv resolves relative paths in the metadata against the
    notebook's directory. Each edit gets its own carrier, deleted when
    the edit finishes. The document is rewritten only if the edit
    succeeds.
    """
    from marimo._utils import yaml

    front = _read_frontmatter(path)

    notebook_dir = os.path.dirname(os.path.abspath(path))
    with _carrier(path, front.header) as target:
        edit(target, notebook_dir)
        with open(target, encoding="utf-8") as f:
            header = f.read()

    data = front.data
    if front.is_pyproject:
        # Strip '# ' and the leading/trailing /// markers
        header = "\n".join(
            [line[2:] for line in header.strip().splitlines()[1:-1]]
        )
        data["pyproject"] = header
    else:
        data["header"] = header

    header = yaml.marimo_compat_dump(data, sort_keys=False)
    document = ["---", header.strip(), "---", front.body]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(document))


@dataclass(frozen=True)
class MaterializedScript:
    """A script uv can operate on and the directory to run uv from."""

    path: str
    directory: str


@contextlib.contextmanager
def materialized_for_environment(path: str) -> Iterator[MaterializedScript]:
    """Materializes a notebook's manifest for environment operations.

    A Python notebook is its own script, so its environment is the one
    `uv run notebook.py` uses and nothing is created. A markdown or
    Quarto notebook writes its header verbatim to the stable carrier
    `.marimo-v<N>-<name>.py` next to the notebook, deleted on exit. uv
    keys a script environment on the script's absolute path, so the
    stable name maps one notebook to one environment, reconciled in
    place across sessions. Concurrent writers produce identical content.
    """
    absolute = os.path.abspath(path)
    directory = os.path.dirname(absolute)
    if not path.endswith((".md", ".qmd")):
        yield MaterializedScript(path=absolute, directory=directory)
        return

    content = (
        "# Generated by marimo; safe to delete.\n"
        + _read_frontmatter(absolute).header
    )
    with _carrier(absolute, content, stable=True) as target:
        yield MaterializedScript(path=target, directory=directory)
