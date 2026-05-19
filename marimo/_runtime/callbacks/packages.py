# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

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

        # Frontend shows package names, not module names
        package_statuses: PackageStatusType = {
            pkg: "queued" for pkg in missing_packages
        }
        broadcast_notification(
            InstallingPackageAlertNotification(
                packages=package_statuses, source=request.source
            )
        )

        def create_log_callback(pkg: str) -> LogCallback:
            def log_callback(log_line: str) -> None:
                broadcast_notification(
                    InstallingPackageAlertNotification(
                        packages=package_statuses,
                        logs={pkg: log_line},
                        log_status="append",
                        source=request.source,
                    ),
                )

            return log_callback

        for pkg in missing_packages:
            if self.package_manager.attempted_to_install(package=pkg):
                # Already attempted an installation; it must have failed.
                # Skip the installation.
                continue
            package_statuses[pkg] = "installing"
            broadcast_notification(
                InstallingPackageAlertNotification(
                    packages=package_statuses, source=request.source
                )
            )

            # Send initial "start" log
            broadcast_notification(
                InstallingPackageAlertNotification(
                    packages=package_statuses,
                    logs={pkg: f"Installing {pkg}...\n"},
                    log_status="start",
                    source=request.source,
                )
            )

            version = request.versions.get(pkg)
            if await self.package_manager.install(
                pkg, version=version, log_callback=create_log_callback(pkg)
            ):
                package_statuses[pkg] = "installed"
                # Send final "done" log
                broadcast_notification(
                    InstallingPackageAlertNotification(
                        packages=package_statuses,
                        logs={pkg: f"Successfully installed {pkg}\n"},
                        log_status="done",
                        source=request.source,
                    ),
                )
            else:
                package_statuses[pkg] = "failed"
                mod = self.package_manager.package_to_module(pkg)
                self._kernel.module_registry.excluded_modules.add(mod)
                # Send final "done" log with error
                broadcast_notification(
                    InstallingPackageAlertNotification(
                        packages=package_statuses,
                        logs={pkg: f"Failed to install {pkg}\n"},
                        log_status="done",
                        source=request.source,
                    ),
                )

        installed_modules = [
            self.package_manager.package_to_module(pkg)
            for pkg in package_statuses
            if package_statuses[pkg] == "installed"
        ]

        # If a package was not installed at cell registration time, it won't
        # yet be in the script metadata.
        if self.should_update_script_metadata():
            self.update_script_metadata(installed_modules)

        # All cells that depend on successfully installed modules are re-run.
        #
        # This consists of cells that either statically reference the installed
        # module, or that previously failed with a ModuleNotFoundError matching
        # an installed module.
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
