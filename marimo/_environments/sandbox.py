# Copyright 2026 Marimo. All rights reserved.
"""The notebook-bound interface to a sandbox environment manager.

Callers use feature operations; synchronization, Manifest carriers, and
manager-specific commands stay behind this module. A notebook sandbox retains
only its source binding and latest Environment. Carriers remain scoped to one
operation and are cleaned by `script_metadata`.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from marimo._environments import script_metadata
from marimo._environments.errors import (
    EnvironmentManagerError,
    SandboxRestartRequired,
)
from marimo._environments.process import run_command

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from marimo._environments.environment import Environment, ProcessPlan
    from marimo._environments.overlay import RuntimeOverlay
    from marimo._environments.script_metadata import MaterializedScript
    from marimo._utils.uv_tree import DependencyTreeNode

Backend = Literal["uv", "pixi"]
SandboxOperation = Literal["prepare", "add", "upgrade", "remove", "sync"]
LogCallback = Callable[[str], None]
ENVIRONMENT_PYTHON = "MARIMO_SANDBOX_ENVIRONMENT_PYTHON"
ENVIRONMENT_ROOT = "MARIMO_SANDBOX_ENVIRONMENT_ROOT"
MANIFEST_SOURCE = "MARIMO_SANDBOX_MANIFEST_SOURCE"


@dataclass(frozen=True)
class ResolvedPackage:
    """A package installed in the synchronized Environment."""

    name: str
    version: str


@dataclass(frozen=True)
class PackageState:
    """The package-panel view of a synchronized notebook sandbox."""

    packages: tuple[ResolvedPackage, ...]
    tree: DependencyTreeNode | None


@dataclass(frozen=True)
class SandboxCommand:
    """A backend command executed on behalf of a sandbox operation."""

    backend: Backend
    operation: SandboxOperation
    argv: tuple[str, ...]


class SandboxReporter(Protocol):
    """Receives operational sandbox reports outside backend output."""

    def report(self, command: SandboxCommand) -> None: ...


class NullSandboxReporter:
    """Suppress sandbox operational reports."""

    def report(self, command: SandboxCommand) -> None:
        del command


class TerminalSandboxReporter:
    """Render sandbox operations to the terminal."""

    def report(self, command: SandboxCommand) -> None:
        from marimo._cli.print import echo, muted

        labels: dict[SandboxOperation, str] = {
            "prepare": "Preparing sandbox",
            "add": "Adding to sandbox",
            "upgrade": "Upgrading in sandbox",
            "remove": "Removing from sandbox",
            "sync": "Synchronizing sandbox",
        }
        echo(
            f"{labels[command.operation]}: "
            f"{muted(shlex.join(_redact_command(command.argv)))}",
            err=True,
        )


class BackendAdapter(Protocol):
    """Operations supplied by a sandbox environment manager."""

    name: Backend

    def ensure_available(self) -> None: ...

    async def ensure_available_async(self) -> None: ...

    def prepare_source(self, source: str) -> None: ...

    async def prepare_source_async(self, source: str) -> None: ...

    async def sync_async(
        self,
        target: MaterializedScript,
        *,
        python_override: str | None,
        on_output: LogCallback | None,
        active_environment: Environment | None = None,
    ) -> Environment: ...

    def add(
        self,
        target: MaterializedScript,
        package: str,
        *,
        upgrade: bool,
        on_output: LogCallback | None,
    ) -> None: ...

    def remove(
        self,
        target: MaterializedScript,
        package: str,
        *,
        on_output: LogCallback | None,
    ) -> None: ...

    def sync(
        self,
        target: MaterializedScript,
        *,
        python_override: str | None,
        on_output: LogCallback | None,
        active_environment: Environment | None = None,
    ) -> Environment: ...

    def packages(
        self,
        target: MaterializedScript,
        environment: Environment | None,
    ) -> PackageState: ...

    def launch(
        self,
        environment: Environment,
        args: Sequence[str],
        *,
        overlay: RuntimeOverlay,
        base_env: Mapping[str, str] | None,
    ) -> ProcessPlan: ...


class NotebookSandbox:
    """A notebook's selected environment manager and latest Environment.

    `launch`, `add`, and `remove` synchronize internally. Package inspection is
    read-only. Rebinding changes the durable source, while package mutations
    continue to synchronize the retained Environment. The next launch acquires
    the new source's path-derived environment identity. No Carrier is retained.
    """

    def __init__(
        self,
        source: str | None,
        backend: Backend,
        *,
        environment: Environment | None = None,
        adapter: BackendAdapter | None = None,
        reporter: SandboxReporter | None = None,
    ) -> None:
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = (
            None
        )
        self._source = self._bind_source(source)
        self._persist_on_rebind = source is None
        self._reporter = reporter or TerminalSandboxReporter()
        if adapter is None:
            from marimo._environments.backends import adapter_for

            adapter = adapter_for(backend, self._reporter)
        self._adapter = adapter
        if self._adapter.name != backend:
            raise ValueError(
                f"Adapter {self._adapter.name!r} cannot manage {backend!r}"
            )
        self._environment = environment
        self._environment_source = (
            self._source if environment is not None else None
        )

    @classmethod
    def from_running_process(
        cls,
        source: str | None,
        backend: Backend,
        *,
        reporter: SandboxReporter | None = None,
    ) -> NotebookSandbox:
        """Bind to the Environment identity exported by `launch`."""
        import os

        from marimo._environments.environment import Environment

        python = os.environ.get(ENVIRONMENT_PYTHON)
        root = os.environ.get(ENVIRONMENT_ROOT)
        environment = (
            Environment(python=python, root=root, action="unchanged")
            if python is not None and root is not None
            else None
        )
        manifest = source or os.environ.get(MANIFEST_SOURCE)
        if manifest is None:
            raise RuntimeError("Running sandbox did not export its manifest")
        sandbox = cls(
            manifest,
            backend,
            environment=environment,
            reporter=reporter,
        )
        # The launcher owns cleanup; the child only persists the manifest
        # when the unnamed notebook is first saved.
        sandbox._persist_on_rebind = source is None
        return sandbox

    @property
    def backend(self) -> Backend:
        return self._adapter.name

    @property
    def source(self) -> str:
        return self._source

    @property
    def environment(self) -> Environment | None:
        return self._environment

    @property
    def environment_source(self) -> str | None:
        """The source that realized the current Environment, if known."""
        return self._environment_source

    def rebind(self, source: str, *, persist_manifest: bool = True) -> None:
        """Bind future operations without changing the running Environment.

        The session persists an unnamed Manifest before notifying its kernel.
        The kernel only follows that binding (`persist_manifest=False`): the
        session may already have released the temporary Manifest.
        """
        import os

        absolute = os.path.abspath(source)
        if absolute == self._source:
            return
        if self._persist_on_rebind:
            if persist_manifest:
                script_metadata.copy_metadata(self._source, absolute)
            self._persist_on_rebind = False
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
            self._temporary_directory = None
        self._source = absolute

    def close(self) -> None:
        """Release an owned Manifest for an unnamed notebook, if any."""
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
            self._temporary_directory = None

    def _bind_source(self, source: str | None) -> str:
        import os

        if source is not None:
            return os.path.abspath(source)

        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="marimo-sandbox-"
        )
        path = os.path.join(self._temporary_directory.name, "notebook.py")
        project = script_metadata.with_python_version_requirement(
            {"dependencies": ["marimo"]}
        )
        with open(path, "w", encoding="utf-8") as manifest:
            manifest.write(script_metadata.dumps(project) + "\n")
        return path

    def launch(
        self,
        args: Sequence[str],
        *,
        overlay: RuntimeOverlay,
        base_env: Mapping[str, str] | None = None,
        python_override: str | None = None,
        on_output: LogCallback | None = None,
    ) -> ProcessPlan:
        """Synchronize and plan `python <args...>` in the Environment."""
        self._adapter.ensure_available()
        script_metadata.ensure_metadata_block(self._source)
        self._adapter.prepare_source(self._source)
        environment = self._sync(
            python_override=python_override, on_output=on_output
        )
        return self._launch_plan(environment, args, overlay, base_env)

    async def launch_async(
        self,
        args: Sequence[str],
        *,
        overlay: RuntimeOverlay,
        base_env: Mapping[str, str] | None = None,
        python_override: str | None = None,
        on_output: LogCallback | None = None,
    ) -> ProcessPlan:
        """Prepare cancellably; publish the environment only after success."""
        await self._adapter.ensure_available_async()
        script_metadata.ensure_metadata_block(self._source)
        await self._adapter.prepare_source_async(self._source)
        async with script_metadata.materialized_for_environment_async(
            self._source
        ) as target:
            environment = await self._adapter.sync_async(
                target, python_override=python_override, on_output=on_output
            )
        self._environment = environment
        self._environment_source = self._source
        return self._launch_plan(environment, args, overlay, base_env)

    async def sync_async(
        self, *, on_output: Callable[[str], None] | None = None
    ) -> None:
        """Apply the saved manifest to the environment used by this kernel."""
        await self._adapter.ensure_available_async()
        async with script_metadata.materialized_for_environment_async(
            self._source
        ) as target:
            requirement = _python_requirement(target, self._environment)
            if requirement is not None:
                assert self._environment is not None
                completed = await run_command(
                    [self._environment.python, "-I", "-S", "--version"]
                )
                _check_python_requirement(requirement, completed)
            environment = await self._adapter.sync_async(
                target,
                python_override=None,
                on_output=on_output,
                active_environment=self._environment,
            )
        self._environment = environment
        self._environment_source = self._source

    def _launch_plan(
        self,
        environment: Environment,
        args: Sequence[str],
        overlay: RuntimeOverlay,
        base_env: Mapping[str, str] | None,
    ) -> ProcessPlan:
        plan = self._adapter.launch(
            environment,
            args,
            overlay=overlay,
            base_env=base_env,
        )
        plan.env[ENVIRONMENT_PYTHON] = environment.python
        plan.env[ENVIRONMENT_ROOT] = environment.root
        plan.env[MANIFEST_SOURCE] = self._source
        return plan

    def add(
        self,
        package: str,
        *,
        upgrade: bool = False,
        on_output: LogCallback | None = None,
    ) -> None:
        """Add or refresh a direct Manifest dependency and synchronize.

        A bare requirement (`polars`, `duckdb[spatial]`) is pinned to the
        version the synchronized Environment resolved (`polars==1.2.3`),
        so a shared notebook reproduces this Environment without a
        lockfile. Requirements the caller constrains -- version
        specifiers, URLs, direct references -- are written as given, and
        marimo itself is never pinned: its version belongs to the
        launching runtime.
        """
        self._adapter.ensure_available()
        bare = _bare_requirement(package)
        if bare is not None and not bare.extras:
            # Re-adding a package without extras must not silently remove
            # extras already declared by the notebook when the resolved
            # version is pinned below.
            bare = self._declared_bare(bare) or bare
        request = package
        if bare is not None and upgrade:
            # Both managers leave an existing Manifest entry alone when a
            # bare name is re-added, so a pin written by an earlier add
            # would hold the version forever. Reopen it to `>=current`;
            # the pin below then records what the new solve chose.
            reopened = self._reopened_requirement(bare)
            if reopened is not None:
                bare, request = reopened
        with script_metadata.metadata_transaction(self._source):
            with script_metadata.materialized_for_edit(self._source) as target:
                self._adapter.add(
                    target,
                    request,
                    upgrade=upgrade,
                    on_output=on_output,
                )
            # Pixi can resolve a newer version than the installed one. Pin
            # that resolution before syncing so success means the final
            # manifest, not an intermediate constraint, was installed.
            if bare is not None:
                self._pin(bare)
            self._sync(
                on_output=on_output, active_environment=self._environment
            )

    def remove(
        self,
        package: str,
        *,
        on_output: LogCallback | None = None,
    ) -> None:
        """Remove a direct Manifest dependency and synchronize."""
        package = _normalize_dependency_name(package)
        if package == "marimo":
            raise script_metadata.ScriptMetadataError(
                "marimo is managed by the sandbox runtime and cannot be removed"
            )
        self._adapter.ensure_available()
        with script_metadata.metadata_transaction(self._source):
            with script_metadata.materialized_for_edit(self._source) as target:
                self._adapter.remove(target, package, on_output=on_output)
            self._sync(
                on_output=on_output, active_environment=self._environment
            )

    def record_dependencies(
        self,
        packages: Sequence[str],
        *,
        runtime_versions: Mapping[str, str],
    ) -> None:
        """Record imported packages without reinstalling the environment.

        Existing declarations retain their constraints, extras, markers, and
        sources. Versions come from the backend or the calling kernel's
        runtime overlay, which can supply otherwise undeclared dependencies.
        """
        requested = {
            _normalize_dependency_name(package) for package in packages
        }
        if not requested:
            return
        requested -= {
            _normalize_dependency_name(dependency)
            for dependency in self._declared_dependencies()
        } | {"marimo"}
        if not requested:
            return
        versions = {
            _normalize_dependency_name(package.name): package.version
            for package in self.packages().packages
        }
        versions.update(
            (_normalize_dependency_name(name), version)
            for name, version in runtime_versions.items()
        )
        requirements = [
            f"{name}=={versions[name]}"
            for name in sorted(requested)
            if versions.get(name)
        ]
        if not requirements:
            return
        with script_metadata.materialized_for_edit(self._source) as target:
            for requirement in requirements:
                self._adapter.add(
                    target, requirement, upgrade=False, on_output=None
                )

    def packages(
        self, *, on_output: LogCallback | None = None
    ) -> PackageState:
        """Inspect the bound Manifest without synchronizing its Environment."""
        del on_output
        self._adapter.ensure_available()
        with script_metadata.materialized_for_environment(
            self._source
        ) as target:
            return self._adapter.packages(target, self._environment)

    def _reopened_requirement(
        self, bare: _BareRequirement
    ) -> tuple[_BareRequirement, str] | None:
        """A `name>=current` rewrite that lets an upgrade's solve advance.

        The floor comes from the Manifest's exact pin when one is
        declared (keeping its extras), otherwise from the synchronized
        Environment. Returns the requirement to pin afterwards and the
        rewrite, or None when no current version is known; the Manifest
        is then already open enough for the solve to move.
        """
        declared = self._declared_pin(bare)
        if declared is not None:
            pinned, version = declared
            return pinned, f"{pinned.text}>={_floor(version)}"
        resolved = self._resolved_version(bare.name)
        if resolved is not None:
            return bare, f"{bare.text}>={_floor(resolved)}"
        return None

    def _declared_bare(
        self, bare: _BareRequirement
    ) -> _BareRequirement | None:
        """The Manifest's spelling of a package name and extras, if any."""
        for dependency in self._declared_dependencies():
            match = _NAMED_REQUIREMENT.match(dependency)
            if match is None:
                continue
            if _normalize_dependency_name(match.group("name")) != bare.name:
                continue
            extras = match.group("extras") or ""
            return _BareRequirement(
                text=f"{match.group('name')}{extras}",
                name=bare.name,
                extras=extras,
            )
        return None

    def _declared_pin(
        self, bare: _BareRequirement
    ) -> tuple[_BareRequirement, str] | None:
        """The Manifest's exact pin for a package, if it declares one."""
        for dependency in self._declared_dependencies():
            match = _EXACT_PIN.match(dependency)
            if match is None:
                continue
            if _normalize_dependency_name(match.group("name")) != bare.name:
                continue
            extras = (
                bare.extras if bare.extras else (match.group("extras") or "")
            )
            return (
                _BareRequirement(
                    text=f"{match.group('name')}{extras}",
                    name=bare.name,
                    extras=extras,
                ),
                match.group("version"),
            )
        return None

    def _declared_dependencies(self) -> list[str]:
        """The Manifest's direct dependency strings."""
        with script_metadata.materialized_for_environment(
            self._source
        ) as target:
            try:
                with open(target.path, encoding="utf-8") as file:
                    project = script_metadata.loads(file.read()) or {}
            except (OSError, ValueError):
                return []
        dependencies = project.get("dependencies", [])
        if not isinstance(dependencies, list):
            return []
        return [str(dependency) for dependency in dependencies]

    def _pin(self, bare: _BareRequirement) -> None:
        """Record the resolved version before synchronizing the Manifest."""
        version = self._resolved_version(bare.name)
        if version is None:
            # Not resolved on this platform (e.g. excluded by a marker);
            # the open requirement stands.
            return
        with script_metadata.materialized_for_edit(self._source) as target:
            self._adapter.add(
                target,
                f"{bare.text}=={version}",
                upgrade=False,
                on_output=None,
            )

    def _resolved_version(self, name: str) -> str | None:
        """The package's version resolved from the current Manifest."""
        with script_metadata.materialized_for_environment(
            self._source
        ) as target:
            state = self._adapter.packages(target, self._environment)
        for package in state.packages:
            if _normalize_dependency_name(package.name) == name:
                return package.version or None
        return None

    def _sync(
        self,
        *,
        python_override: str | None = None,
        on_output: LogCallback | None = None,
        active_environment: Environment | None = None,
    ) -> Environment:
        with script_metadata.materialized_for_environment(
            self._source
        ) as target:
            requirement = _python_requirement(target, active_environment)
            if requirement is not None:
                assert active_environment is not None
                completed = subprocess.run(
                    [active_environment.python, "-I", "-S", "--version"],
                    capture_output=True,
                    text=True,
                )
                _check_python_requirement(requirement, completed)
            environment = self._adapter.sync(
                target,
                python_override=python_override,
                on_output=on_output,
                active_environment=active_environment,
            )
        self._environment = environment
        self._environment_source = self._source
        return environment


def _python_requirement(
    target: MaterializedScript, active_environment: Environment | None
) -> str | None:
    if active_environment is None:
        return None
    project = script_metadata.loads(Path(target.path).read_text("utf-8"))
    requirement = (
        project.get("requires-python") if project is not None else None
    )
    if requirement is not None and not isinstance(requirement, str):
        raise script_metadata.ScriptMetadataError(
            "requires-python must be a version specifier string"
        )
    return requirement


def _check_python_requirement(
    requirement: str, completed: subprocess.CompletedProcess[str]
) -> None:
    from packaging.specifiers import InvalidSpecifier, SpecifierSet

    try:
        specifier = SpecifierSet(requirement)
    except InvalidSpecifier as error:
        raise script_metadata.ScriptMetadataError(
            f"Invalid requires-python: {requirement}"
        ) from error
    if completed.returncode != 0:
        raise EnvironmentManagerError(
            "Could not determine the active sandbox's Python version.\n"
            + completed.stderr
        )
    version = completed.stdout.strip().removeprefix("Python ")
    if not specifier.contains(version, prereleases=True):
        raise SandboxRestartRequired(
            f"The manifest requires Python {requirement}, but the running "
            f"kernel uses Python {version}. Restart the kernel to apply "
            "the new Python requirement."
        )


def _normalize_dependency_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement.strip())
    if match is None:
        return requirement.lower()
    return re.sub(r"[-_.]+", "-", match.group(0)).lower()


@dataclass(frozen=True)
class _BareRequirement:
    """A requirement that names a package without constraining it."""

    # The requirement as requested: name plus any extras.
    text: str
    # The PEP 503 normalized package name.
    name: str
    extras: str


_BARE_REQUIREMENT = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?\s*$"
)

_NAMED_REQUIREMENT = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?"
)

# An exact pin holds one release: `name==1.2.3`, optionally with extras,
# an epoch, or a local segment -- but not a wildcard (`==1.*`), which is
# a range.
_EXACT_PIN = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?"
    r"\s*==\s*(?P<version>[A-Za-z0-9!+.]+)\s*$"
)


def _bare_requirement(package: str) -> _BareRequirement | None:
    """Parse `name` or `name[extras]`; None for anything more specific.

    marimo also returns None: its version is the runtime's to manage,
    never the Manifest's.
    """
    match = _BARE_REQUIREMENT.match(package)
    if match is None:
        return None
    name = _normalize_dependency_name(match.group("name"))
    if name == "marimo":
        return None
    extras = match.group("extras") or ""
    return _BareRequirement(
        text=f"{match.group('name')}{extras}", name=name, extras=extras
    )


def _floor(version: str) -> str:
    """A version usable as a `>=` floor.

    PEP 440 forbids local segments (`1.2+cpu`) in ordered comparisons,
    so the floor is the public part.
    """
    return version.split("+", 1)[0]


_URL_CREDENTIALS = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@"
)


def _redact_command(command: Sequence[str]) -> list[str]:
    """Redact URL userinfo before rendering a command."""
    return [_redact_url_credentials(argument) for argument in command]


def _redact_url_credentials(value: str) -> str:
    """Replace URL userinfo embedded in text with a placeholder."""
    return _URL_CREDENTIALS.sub(r"\g<scheme>***@", value)
