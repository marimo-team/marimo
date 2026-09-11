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
import errno
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import time
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
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s"
    r"(?P<content>(^#(?! ///$)(| .*)$\s)+)^# ///$"
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
    from marimo._utils import yaml
    from marimo._utils.inline_script_metadata import (
        get_headers_from_frontmatter,
    )

    with open(path, encoding="utf-8", newline="") as f:
        content = f.read()
    data, _ = extract_frontmatter(content)
    match = yaml.YAML_FRONT_MATTER_REGEX.match(content)
    # Preserve everything after the closing marker, including its newline.
    body = content[match.end(1) + len("---") :] if match else "\n" + content
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


_CARRIER_VERSION = 1


def _carrier_prefix(path: str) -> str:
    return f".marimo-v{_CARRIER_VERSION}-{os.path.basename(path)}"


@contextlib.contextmanager
def _stable_carrier_lock(path: str) -> Iterator[None]:
    """Hold an OS lock through creation, use, and removal of the carrier.

    The lock file stays in place: unlinking it would let a new caller lock
    a different inode while existing callers still wait on the old one.
    Process exit releases the lock, including after a crash.
    """
    target = Path(path).with_name(f"{_carrier_prefix(path)}.lock")
    # Never truncate or follow a pre-existing link, even for the lock file.
    if target.is_symlink():
        raise OSError(f"Refusing to use symlink as carrier lock: {target}")
    descriptor = os.open(
        target, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    with os.fdopen(descriptor, "r+b", buffering=0) as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise OSError(f"Carrier lock is not a regular file: {target}")
        if sys.platform == "win32":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EDEADLK):
                        raise
                    time.sleep(0.05)
            try:
                yield
            finally:
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def _carrier(
    notebook: str, content: str, *, stable: bool = False
) -> Iterator[str]:
    """Materialize beside the notebook so uv preserves path semantics.

    Stable callers must hold `_stable_carrier_lock` for the full lifetime.
    Only that carrier can be reclaimed after a crash; age alone cannot
    distinguish another operation's active carrier from an abandoned one.
    """
    absolute = os.path.abspath(notebook)
    directory = os.path.dirname(absolute)
    try:
        if stable:
            target = os.path.join(directory, f"{_carrier_prefix(absolute)}.py")
            if os.path.islink(target):
                raise OSError(f"Refusing to replace carrier symlink: {target}")
            # The lock proves no cooperating process is still using it.
            with contextlib.suppress(FileNotFoundError):
                os.unlink(target)
            descriptor = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
        else:
            descriptor, target = tempfile.mkstemp(
                dir=directory,
                prefix=f"{_carrier_prefix(absolute)}.",
                suffix=".py",
            )
    except OSError as error:
        raise ScriptMetadataError(
            f"Cannot create a metadata carrier beside {notebook}. "
            "Make the notebook directory writable and remove any "
            "conflicting carrier symlinks."
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            f.write(content)
        yield target
    finally:
        try:
            os.unlink(target)
        except OSError:
            LOGGER.debug("Could not remove carrier %s", target)


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
    document = f"---\n{header.strip()}\n---{front.body}"
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(document)


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
    place across sessions. An OS lock serializes carrier lifetimes across
    threads and processes.
    """
    absolute = os.path.abspath(path)
    directory = os.path.dirname(absolute)
    if not path.endswith((".md", ".qmd")):
        yield MaterializedScript(path=absolute, directory=directory)
        return

    with contextlib.ExitStack() as stack:
        try:
            stack.enter_context(_stable_carrier_lock(absolute))
        except OSError as error:
            raise ScriptMetadataError(
                f"Cannot lock a metadata carrier beside {path}. "
                "Make the notebook directory writable and remove any "
                "conflicting carrier lock symlinks."
            ) from error
        content = (
            "# Generated by marimo; safe to delete.\n"
            + _read_frontmatter(absolute).header
        )
        with _carrier(absolute, content, stable=True) as target:
            yield MaterializedScript(path=target, directory=directory)
