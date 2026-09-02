# Copyright 2026 Marimo. All rights reserved.
"""The uv and pixi environment-manager adapters.

`UvBackendAdapter` and `PixiBackendAdapter` supply the notebook sandbox's
backend operations; `adapter_for` selects one. The module-level
verbs plan launches for callers that must not edit a manifest (an app
host serving notebooks); they dispatch through the same adapters, so
backend policy lives in one place.

Both managers honor the runtime overlay: uv layers it directly via
`uv run --with`, while pixi routes the same layering through
`pixi exec uv run`, whose ephemeral environment chains the conda
prefix's site-packages. Either way the manifest carries only a loose
`marimo` (for standalone runs) and the overlay supplies the running
version.

SINGLE and MULTI sandbox modes are topologies, not engines: they differ
in which process gets launched, not in how environments are made.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from marimo import _loggers

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from marimo._environments.environment import Environment, ProcessPlan
    from marimo._environments.overlay import RuntimeOverlay
    from marimo._environments.sandbox import (
        Backend,
        BackendAdapter,
        LogCallback,
        PackageState,
        ResolvedPackage,
        SandboxOperation,
        SandboxReporter,
    )
    from marimo._environments.script_metadata import MaterializedScript
    from marimo._utils.uv_tree import DependencyTreeNode

LOGGER = _loggers.marimo_logger()


def current_backend() -> Backend:
    """The backend this process was sandboxed with; uv when unset."""
    from marimo._config.settings import GLOBAL_SETTINGS

    return "pixi" if GLOBAL_SETTINGS.SANDBOX_BACKEND == "pixi" else "uv"


def adapter_for(
    backend: Backend, reporter: SandboxReporter | None = None
) -> BackendAdapter:
    """The adapter managing `backend`'s environments.

    Constructing an adapter is backend-pure: selecting pixi does not
    import or probe the uv implementation, and vice versa.
    """
    if backend == "pixi":
        return PixiBackendAdapter(reporter)
    return UvBackendAdapter(reporter)


def ensure_available(backend: Backend) -> None:
    """Raise unless the backend's executable is usable and supported.

    uv raises `UvNotFoundError` or `UvUnsupportedVersionError`; pixi
    raises `PixiNotFoundError` or `PixiUnsupportedVersionError`.
    """
    adapter_for(backend).ensure_available()


def sync_notebook(
    path: str,
    *,
    backend: Backend,
    python_override: str | None = None,
    on_output: Callable[[str], None] | None = None,
) -> Environment:
    """Synchronizes a notebook's script environment.

    Raises the backend's error type on failure; both derive from the
    backend's base error (`UvError`, `PixiError`).
    """
    from marimo._environments import script_metadata

    adapter = adapter_for(backend)
    with script_metadata.materialized_for_environment(path) as target:
        return adapter.sync(
            target, python_override=python_override, on_output=on_output
        )


def launch(
    environment: Environment,
    args: Sequence[str],
    *,
    backend: Backend,
    overlay: RuntimeOverlay,
    base_env: Mapping[str, str] | None = None,
) -> ProcessPlan:
    """Plans `python <args...>` inside a synchronized environment."""
    return adapter_for(backend).launch(
        environment, args, overlay=overlay, base_env=base_env
    )


def launch_fallback(
    args: Sequence[str],
    *,
    base_env: Mapping[str, str] | None = None,
) -> ProcessPlan:
    """Plans `python <args...>` for a target without a manifest.

    No manifest means nothing to sandbox: the process runs from this
    interpreter, which has marimo by definition. No environment manager
    selects the interpreter here, so the inherited activation state
    must describe this interpreter: a stale VIRTUAL_ENV from an
    enclosing shell must not leak, and a virtualenv interpreter names
    its own prefix.
    """
    from marimo._environments.environment import ProcessPlan

    env = dict(os.environ if base_env is None else base_env)
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    if sys.prefix != sys.base_prefix:
        env["VIRTUAL_ENV"] = sys.prefix
    return ProcessPlan(argv=(sys.executable, *args), env=env)


class _ReportingBackendAdapter:
    name: Backend

    def __init__(self, reporter: SandboxReporter | None = None) -> None:
        if reporter is None:
            from marimo._environments.sandbox import NullSandboxReporter

            reporter = NullSandboxReporter()
        self._reporter = reporter

    def _report(
        self, operation: SandboxOperation, command: Sequence[str]
    ) -> None:
        from marimo._environments.sandbox import SandboxCommand

        self._reporter.report(
            SandboxCommand(
                backend=self.name,
                operation=operation,
                argv=tuple(command),
            )
        )


class UvBackendAdapter(_ReportingBackendAdapter):
    """uv implementation of the notebook sandbox backend."""

    name: Backend = "uv"

    def ensure_available(self) -> None:
        from marimo._environments.environment import ensure_supported_uv

        ensure_supported_uv()

    def prepare_source(self, source: str) -> None:
        import subprocess

        from marimo._environments import script_metadata

        try:
            script_metadata.ensure_marimo(
                source,
                on_command=lambda command: self._report("prepare", command),
            )
        except subprocess.TimeoutExpired:
            LOGGER.warning("Timed out adding marimo to script metadata")
        except Exception as error:
            LOGGER.warning(
                "Failed to add marimo to script metadata: %s", error
            )

    def add(
        self,
        target: MaterializedScript,
        package: str,
        *,
        upgrade: bool,
        on_output: LogCallback | None,
    ) -> None:
        from marimo._environments.uv import script_command_env, uv, uv_stream

        command = [
            "add",
            "--script",
            target.path,
            *(["--upgrade"] if upgrade else []),
            package,
        ]

        def report(argv: Sequence[str]) -> None:
            self._report("upgrade" if upgrade else "add", argv)

        if on_output is None:
            uv(
                ["--quiet", *command],
                env=script_command_env(),
                cwd=target.directory,
                on_command=report,
            )
        else:
            uv_stream(
                command,
                on_output,
                env=script_command_env(),
                cwd=target.directory,
                on_command=report,
            )

    def remove(
        self,
        target: MaterializedScript,
        package: str,
        *,
        on_output: LogCallback | None,
    ) -> None:
        from marimo._environments.uv import script_command_env, uv, uv_stream

        command = ["remove", "--script", target.path, package]

        def report(argv: Sequence[str]) -> None:
            self._report("remove", argv)

        if on_output is None:
            uv(
                ["--quiet", *command],
                env=script_command_env(),
                cwd=target.directory,
                on_command=report,
            )
        else:
            uv_stream(
                command,
                on_output,
                env=script_command_env(),
                cwd=target.directory,
                on_command=report,
            )

    def sync(
        self,
        target: MaterializedScript,
        *,
        python_override: str | None,
        on_output: LogCallback | None,
    ) -> Environment:
        from marimo._environments.environment import sync

        return sync(
            target.path,
            cwd=target.directory,
            python_override=python_override,
            on_output=on_output,
            on_command=lambda argv: self._report("sync", argv),
        )

    def packages(
        self,
        target: MaterializedScript,
        environment: Environment | None,
    ) -> PackageState:
        del environment
        from marimo._environments.sandbox import PackageState
        from marimo._environments.uv import UvError, script_command_env, uv
        from marimo._utils.uv_tree import parse_uv_tree

        try:
            completed = uv(
                ["tree", "--no-dedupe", "--script", target.path],
                env=script_command_env(),
                cwd=target.directory,
            )
        except UvError:
            return PackageState(packages=(), tree=None)
        tree = parse_uv_tree(completed.stdout)
        return PackageState(packages=_flatten_tree(tree), tree=tree)

    def launch(
        self,
        environment: Environment,
        args: Sequence[str],
        *,
        overlay: RuntimeOverlay,
        base_env: Mapping[str, str] | None,
    ) -> ProcessPlan:
        from marimo._environments.environment import launch

        return launch(
            environment,
            args,
            overlay=overlay,
            base_env=base_env,
        )


class PixiBackendAdapter(_ReportingBackendAdapter):
    """pixi implementation of the notebook sandbox backend."""

    name: Backend = "pixi"

    def ensure_available(self) -> None:
        from marimo._environments import pixi

        pixi.require_pixi_bin()
        pixi.ensure_supported_pixi()

    def prepare_source(self, source: str) -> None:
        from marimo._environments import pixi

        pixi.ensure_marimo(
            source,
            on_command=lambda command: self._report("prepare", command),
        )

    def add(
        self,
        target: MaterializedScript,
        package: str,
        *,
        upgrade: bool,
        on_output: LogCallback | None,
    ) -> None:
        from marimo._environments import pixi

        pixi.add(
            target.path,
            package,
            cwd=target.directory,
            upgrade=upgrade,
            on_output=on_output,
            on_command=lambda command: self._report(
                "upgrade" if upgrade else "add", command
            ),
        )

    def remove(
        self,
        target: MaterializedScript,
        package: str,
        *,
        on_output: LogCallback | None,
    ) -> None:
        from marimo._environments import pixi

        pixi.remove(
            target.path,
            package,
            cwd=target.directory,
            on_output=on_output,
            on_command=lambda command: self._report("remove", command),
        )

    def sync(
        self,
        target: MaterializedScript,
        *,
        python_override: str | None,
        on_output: LogCallback | None,
    ) -> Environment:
        from marimo._environments import pixi

        if python_override is not None:
            raise pixi.PixiError(
                "pixi sandboxes do not support a Python version override"
            )
        return pixi.sync(
            target.path,
            cwd=target.directory,
            on_output=on_output,
            on_command=lambda command: self._report("sync", command),
        )

    def packages(
        self,
        target: MaterializedScript,
        environment: Environment | None,
    ) -> PackageState:
        del environment
        from marimo._environments import pixi
        from marimo._environments.sandbox import PackageState, ResolvedPackage

        records = pixi.list_script_packages(target.path, cwd=target.directory)
        packages = tuple(
            sorted(
                (
                    ResolvedPackage(
                        name=str(record.get("name", "")),
                        version=str(record.get("version", "")),
                    )
                    for record in records
                    if record.get("name")
                ),
                key=lambda package: package.name,
            )
        )
        return PackageState(
            packages=packages,
            tree=_pixi_tree(records),
        )

    def launch(
        self,
        environment: Environment,
        args: Sequence[str],
        *,
        overlay: RuntimeOverlay,
        base_env: Mapping[str, str] | None,
    ) -> ProcessPlan:
        from marimo._environments import pixi

        return pixi.launch(
            environment, args, overlay=overlay, base_env=base_env
        )


def _flatten_tree(tree: object) -> tuple[ResolvedPackage, ...]:
    from marimo._environments.sandbox import ResolvedPackage
    from marimo._utils.uv_tree import DependencyTreeNode

    if not isinstance(tree, DependencyTreeNode):
        return ()
    seen: set[str] = set()
    packages: list[ResolvedPackage] = []
    stack = list(tree.dependencies)
    while stack:
        node = stack.pop()
        if node.name not in seen:
            seen.add(node.name)
            packages.append(
                ResolvedPackage(name=node.name, version=node.version or "")
            )
        stack.extend(node.dependencies)
    return tuple(sorted(packages, key=lambda package: package.name))


def _pixi_tree(records: list[dict[str, object]]) -> DependencyTreeNode:
    import re

    from marimo._utils.uv_tree import (
        DependencyTag,
        DependencyTreeNode,
    )

    by_name = {
        _normalize_package_name(str(record["name"])): record
        for record in records
        if record.get("name")
    }

    def node_for(name: str, stack: frozenset[str]) -> DependencyTreeNode:
        normalized = _normalize_package_name(name)
        record = by_name.get(normalized, {"name": name})
        tags = []
        kind = record.get("kind")
        if kind:
            tags.append(DependencyTag(kind="kind", value=str(kind)))
        if normalized in stack:
            tags.append(DependencyTag(kind="cycle", value="true"))
            return DependencyTreeNode(
                name=str(record.get("name", name)),
                version=str(record.get("version", "")) or None,
                tags=tags,
                dependencies=[],
            )

        dependencies = []
        for dependency in record.get("depends", []) or []:
            match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(dependency))
            if (
                match is not None
                and _normalize_package_name(match.group(0)) in by_name
            ):
                dependencies.append(
                    node_for(match.group(0), stack | {normalized})
                )
        return DependencyTreeNode(
            name=str(record.get("name", name)),
            version=str(record.get("version", "")) or None,
            tags=tags,
            dependencies=dependencies,
        )

    roots = [
        node_for(str(record["name"]), frozenset())
        for record in records
        if record.get("name") and record.get("is_explicit") is True
    ]
    return DependencyTreeNode(
        name="<root>", version=None, tags=[], dependencies=roots
    )


def _normalize_package_name(name: str) -> str:
    import re

    return re.sub(r"[-_.]+", "-", name).lower()
