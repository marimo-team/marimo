# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._messaging.context import is_code_mode_request
from marimo._messaging.notification import (
    CompletedRunNotification,
    InstallingPackageAlertNotification,
    MissingPackageAlertNotification,
    PackageStatusType,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.commands import InstallPackagesCommand
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.packages.import_error_extractors import (
    extract_missing_module_from_cause_chain,
    try_extract_packages_from_import_error_message,
)
from marimo._runtime.packages.package_manager import (
    LogCallback,
    PackageManager,
)
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.utils import (
    PackageRequirement,
    is_python_isolated,
)
from marimo._runtime.runner import hook_context

if TYPE_CHECKING:
    from marimo._messaging.types import Stream
    from marimo._runtime.request_router import RequestRouter
    from marimo._runtime.runtime import Kernel

LOGGER = _loggers.marimo_logger()


class PackagesCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel
        self.package_manager: PackageManager | None = None

    def register(self, router: RequestRouter) -> None:
        router.register(InstallPackagesCommand, self._handle_install)

    async def _handle_install(self, request: InstallPackagesCommand) -> None:
        if request.explicit:
            await self.install_packages(request)
        else:
            await self.install_missing_packages(request)
        broadcast_notification(CompletedRunNotification())

    def update_package_manager(self, package_manager: str) -> None:
        if (
            self.package_manager is None
            or package_manager != self.package_manager.name
        ):
            self.package_manager = create_package_manager(package_manager)

            # All marimo notebooks depend on the marimo package; if the
            # notebook already has marimo as a dependency, or an optional
            # dependency group with marimo, such as marimo[sql], this is a
            # NOOP.
            self._maybe_add_marimo_to_script_metadata()

    def send_missing_packages_alert(self, missing_packages: set[str]) -> None:
        if self.package_manager is None:
            return

        packages = sorted(
            pkg
            for mod in missing_packages
            if not self.package_manager.attempted_to_install(
                pkg := self.package_manager.module_to_package(mod)
            )
        )
        # Deleting a cell can make the set of missing packages smaller
        broadcast_notification(
            MissingPackageAlertNotification(
                packages=packages,
                isolated=is_python_isolated(),
            ),
        )

    def missing_packages_hook(
        self, ctx: hook_context.OnFinishHookContext
    ) -> None:
        module_not_found_errors = [
            e
            for e in ctx.exceptions.values()
            if isinstance(e, (ImportError, ManyModulesNotFoundError))
        ]

        if len(module_not_found_errors) == 0:
            return

        if self.package_manager is None:
            return

        missing_modules: set[str] = set()
        missing_packages: set[str] = set()

        # Populate missing_modules and missing_packages from the errors
        for e in module_not_found_errors:
            if isinstance(e, ManyModulesNotFoundError):
                # filter out packages that we already attempted to install
                # to prevent an infinite loop
                missing_packages.update(
                    {
                        pkg
                        for pkg in e.package_names
                        if not self.package_manager.attempted_to_install(pkg)
                    }
                )
                continue

            maybe_missing_module = extract_missing_module_from_cause_chain(e)
            if maybe_missing_module:
                missing_modules.add(maybe_missing_module)
                continue

            maybe_missing_packages = (
                try_extract_packages_from_import_error_message(str(e))
            )
            if maybe_missing_packages:
                missing_packages.update(
                    {
                        pkg
                        for pkg in maybe_missing_packages
                        if not self.package_manager.attempted_to_install(pkg)
                    }
                )

        # Grab missing modules from module registry and from module not found errors
        missing_modules = (
            self._kernel.module_registry.missing_modules() | missing_modules
        )

        # Convert modules to packages
        for mod in missing_modules:
            pkg = self.package_manager.module_to_package(mod)
            # filter out packages that we already attempted to install
            # to prevent an infinite loop
            if not self.package_manager.attempted_to_install(pkg):
                missing_packages.add(pkg)

        if not missing_packages:
            return

        packages = sorted(missing_packages)
        if self.package_manager.should_auto_install():
            version = {pkg: "" for pkg in packages}
            self._kernel.enqueue_control_request(
                InstallPackagesCommand(
                    manager=self.package_manager.name, versions=version
                )
            )
        else:
            if is_code_mode_request():
                return

            broadcast_notification(
                MissingPackageAlertNotification(
                    packages=packages,
                    isolated=is_python_isolated(),
                ),
            )

    async def _stream_install(
        self,
        packages: list[str],
        versions: dict[str, str],
        *,
        source: Literal["kernel", "server"],
        upgrade: bool = False,
        group: str | None = None,
        skip_attempted: bool = True,
    ) -> PackageStatusType:
        """Install packages, streaming progress to the install overlay.

        Broadcasts `InstallingPackageAlertNotification`s as each package moves
        through queued -> installing -> installed/failed, streaming the package
        manager's output as it runs. Returns the final per-package status map.

        This is the shared engine for both the on-import missing-packages flow
        and explicit installs from the packages panel; it deliberately performs
        no module-registry bookkeeping or cell re-runs (callers handle those).
        """
        assert self.package_manager is not None, (
            "Cannot install packages without a package manager"
        )
        package_manager = self.package_manager

        # `install` streams logs from a worker thread (it runs via
        # asyncio.to_thread). The runtime context is thread-local, so we
        # capture the stream here -- on the kernel thread -- and pass it
        # explicitly to every broadcast; otherwise log lines emitted from the
        # worker thread can't resolve a context and are silently dropped.
        try:
            stream: Stream | None = get_context().stream
        except ContextNotInitializedError:
            stream = None

        package_statuses: PackageStatusType = {
            pkg: "queued" for pkg in packages
        }
        broadcast_notification(
            InstallingPackageAlertNotification(
                packages=package_statuses, source=source
            ),
            stream=stream,
        )

        def create_log_callback(pkg: str) -> LogCallback:
            def log_callback(log_line: str) -> None:
                broadcast_notification(
                    InstallingPackageAlertNotification(
                        packages=package_statuses,
                        logs={pkg: log_line},
                        log_status="append",
                        source=source,
                    ),
                    stream=stream,
                )

            return log_callback

        for pkg in packages:
            if skip_attempted and package_manager.attempted_to_install(
                package=pkg
            ):
                # Already attempted an installation; it must have failed.
                # Skip the installation.
                continue
            package_statuses[pkg] = "installing"
            broadcast_notification(
                InstallingPackageAlertNotification(
                    packages=package_statuses, source=source
                ),
                stream=stream,
            )

            # Send initial "start" log
            broadcast_notification(
                InstallingPackageAlertNotification(
                    packages=package_statuses,
                    logs={pkg: f"Installing {pkg}...\n"},
                    log_status="start",
                    source=source,
                ),
                stream=stream,
            )

            if await package_manager.install(
                pkg,
                version=versions.get(pkg),
                upgrade=upgrade,
                group=group,
                log_callback=create_log_callback(pkg),
            ):
                package_statuses[pkg] = "installed"
                # Send final "done" log
                broadcast_notification(
                    InstallingPackageAlertNotification(
                        packages=package_statuses,
                        logs={pkg: f"Successfully installed {pkg}\n"},
                        log_status="done",
                        source=source,
                    ),
                    stream=stream,
                )
            else:
                package_statuses[pkg] = "failed"
                # Send final "done" log with error
                broadcast_notification(
                    InstallingPackageAlertNotification(
                        packages=package_statuses,
                        logs={pkg: f"Failed to install {pkg}\n"},
                        log_status="done",
                        source=source,
                    ),
                    stream=stream,
                )

        return package_statuses

    async def _rerun_cells_for_installed(
        self, installed_modules: list[str]
    ) -> None:
        """Re-run cells affected by successfully installed modules.

        This consists of cells that either statically reference an installed
        module, or that previously failed with a `ModuleNotFoundError` matching
        an installed module.
        """
        cells_to_run = {
            cid
            for module in installed_modules
            if (cid := self._kernel.module_registry.defining_cell(module))
            is not None
        }

        for cid, cell in self._kernel.graph.cells.items():
            if (
                isinstance(cell.exception, ModuleNotFoundError)
                and cell.exception.name in installed_modules
            ):
                cells_to_run.add(cid)

        if cells_to_run:
            await self._kernel.maybe_autorun_cells(cells_to_run)

    async def install_missing_packages(
        self, request: InstallPackagesCommand
    ) -> None:
        """Attempts to install packages for modules that cannot be imported

        Runs cells affected by successful installation.
        """
        assert self.package_manager is not None, (
            "Cannot install packages without a package manager"
        )
        if request.manager != self.package_manager.name:
            # Swap out the package manager
            self.package_manager = create_package_manager(request.manager)

        if not self.package_manager.is_manager_installed():
            self.package_manager.alert_not_installed()
            return

        resolved_packages: dict[str, PackageRequirement] = {}
        for pkg in request.versions:
            pkg_req = PackageRequirement.parse(pkg)
            resolved_packages[pkg_req.name] = pkg_req

        # Append all other missing packages from the notebook; the missing
        # package request only contains the packages from the cell the user
        # executed.
        for module in self._kernel.module_registry.missing_modules():
            pkg_req = PackageRequirement.parse(
                self.package_manager.module_to_package(module)
            )
            if pkg_req.name not in resolved_packages:
                resolved_packages[pkg_req.name] = pkg_req

        # Convert back to list of package strings
        missing_packages = [
            str(pkg)
            for pkg in sorted(resolved_packages.values(), key=lambda p: p.name)
        ]

        package_statuses = await self._stream_install(
            missing_packages,
            request.versions,
            source=request.source,
            skip_attempted=True,
        )

        # Exclude modules whose package failed to install so we don't
        # repeatedly prompt for them.
        for pkg, status in package_statuses.items():
            if status == "failed":
                mod = self.package_manager.package_to_module(pkg)
                self._kernel.module_registry.excluded_modules.add(mod)

        installed_modules = [
            self.package_manager.package_to_module(pkg)
            for pkg, status in package_statuses.items()
            if status == "installed"
        ]

        # If a package was not installed at cell registration time, it won't
        # yet be in the script metadata.
        if self.should_update_script_metadata():
            self.update_script_metadata(installed_modules)

        await self._rerun_cells_for_installed(installed_modules)

    async def install_packages(self, request: InstallPackagesCommand) -> None:
        """Install packages requested explicitly (e.g. from the packages panel).

        Unlike `install_missing_packages`, this installs only the requested
        packages, retries previously-failed installs, and does not exclude
        modules on failure. Progress and errors stream to the install overlay.
        """
        if (
            self.package_manager is None
            or request.manager != self.package_manager.name
        ):
            self.package_manager = create_package_manager(request.manager)

        if not self.package_manager.is_manager_installed():
            self.package_manager.alert_not_installed()
            return

        packages = list(request.versions.keys())
        package_statuses = await self._stream_install(
            packages,
            request.versions,
            source=request.source,
            upgrade=request.upgrade,
            group=request.group,
            skip_attempted=False,
        )

        installed_specs = [
            pkg
            for pkg, status in package_statuses.items()
            if status == "installed"
        ]

        # Record the exact specs (preserving version pins, extras, URLs) in the
        # notebook's inline script metadata.
        if installed_specs and self.should_update_script_metadata():
            filename = self._kernel.app_metadata.filename
            if filename:
                try:
                    self.package_manager.update_notebook_script_metadata(
                        filepath=filename,
                        packages_to_add=installed_specs,
                        upgrade=request.upgrade,
                    )
                except Exception as e:
                    LOGGER.error(
                        "Failed to add script metadata to notebook: %s", e
                    )

        # Re-run cells that statically reference, or previously failed to
        # import, a now-installed module. Spec parsing is best-effort.
        installed_modules: list[str] = []
        for spec in installed_specs:
            try:
                name = PackageRequirement.parse(spec).name
            except Exception:
                continue
            installed_modules.append(
                self.package_manager.package_to_module(name)
            )
        await self._rerun_cells_for_installed(installed_modules)

    def _maybe_add_marimo_to_script_metadata(self) -> None:
        if self.should_update_script_metadata():
            self.update_script_metadata(["marimo"])

    def should_update_script_metadata(self) -> bool:
        return (
            GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA is True
            and self._kernel.app_metadata.filename is not None
            and self.package_manager is not None
        )

    def update_script_metadata(
        self, import_namespaces_to_add: list[str]
    ) -> None:
        filename = self._kernel.app_metadata.filename

        if not filename or not self.package_manager:
            return

        try:
            LOGGER.debug(
                "Updating script metadata: %s. Adding namespaces: %s.",
                filename,
                import_namespaces_to_add,
            )
            self.package_manager.update_notebook_script_metadata(
                filepath=filename,
                import_namespaces_to_add=import_namespaces_to_add,
                upgrade=False,
            )
        except Exception as e:
            LOGGER.error("Failed to add script metadata to notebook: %s", e)
