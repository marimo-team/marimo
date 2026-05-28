# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._runtime.commands import InstallPackagesCommand
from marimo._runtime.packages.package_manager import PackageManager
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.utils import split_packages
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.packages import (
    AddPackageRequest,
    DependencyTreeResponse,
    ListPackagesResponse,
    PackageOperationResponse,
    RemovePackageRequest,
)
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for packages endpoints
router = APIRouter()

# Matches ANSI escape sequences (color codes, etc.) emitted by package managers.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Package-manager failures (e.g. dependency resolution conflicts) can be
# hundreds of lines; the actionable error is almost always at the end, so we
# only surface the tail to keep the error toast readable.
_MAX_ERROR_LINES = 30


def _format_install_error(output: str, *, fallback: str) -> str:
    """Strip ANSI codes and return the tail of package-manager output.

    Falls back to `fallback` when no output was captured.
    """
    cleaned = _ANSI_ESCAPE_RE.sub("", output).strip()
    if not cleaned:
        return fallback
    lines = cleaned.splitlines()
    if len(lines) > _MAX_ERROR_LINES:
        lines = ["...", *lines[-_MAX_ERROR_LINES:]]
    return "\n".join(lines)


@router.post("/add")
@requires("edit")
async def add_package(request: Request) -> PackageOperationResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/AddPackageRequest"
    responses:
        200:
            description: Install package
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/PackageOperationResponse"
    """
    body = await parse_request(request, cls=AddPackageRequest)

    app_state = AppState(request)
    session = app_state.get_current_session()

    upgrade = body.upgrade or False
    group = body.group or None

    if session is not None:
        # Route the install through the kernel so that progress and errors
        # stream into the package-install overlay -- the same experience as
        # installing missing packages detected on import.
        versions = {pkg: "" for pkg in split_packages(body.package)}
        session.put_control_request(
            InstallPackagesCommand(
                manager=app_state.app_config_manager.package_manager,
                versions=versions,
                explicit=True,
                upgrade=upgrade,
                group=group,
            ),
            from_consumer_id=ConsumerId(
                app_state.require_current_session_id()
            ),
        )
        return PackageOperationResponse.of_success()

    # No active session (e.g. non-interactive contexts): install synchronously
    # and surface any error directly in the response.
    package_manager = _get_package_manager(request)
    if not package_manager.is_manager_installed():
        package_manager.alert_not_installed()
        return PackageOperationResponse.of_failure(
            f"{package_manager.name} is not available. "
            f"Check out the docs for installation instructions: {package_manager.docs_url}"
        )

    output_lines: list[str] = []
    success = await package_manager.install(
        body.package,
        version=None,
        upgrade=upgrade,
        group=group,
        log_callback=output_lines.append,
    )

    # Update the script metadata
    filename = _get_filename(request)
    if filename is not None and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        await asyncio.to_thread(
            package_manager.update_notebook_script_metadata,
            filepath=filename,
            packages_to_add=split_packages(body.package),
            upgrade=upgrade,
        )

    if success:
        return PackageOperationResponse.of_success()

    return PackageOperationResponse.of_failure(
        _format_install_error(
            "".join(output_lines),
            fallback=(
                f"Failed to install {body.package}. "
                "See terminal for error logs."
            ),
        )
    )


@router.post("/remove")
@requires("edit")
async def remove_package(request: Request) -> PackageOperationResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/RemovePackageRequest"
    responses:
        200:
            description: Uninstall package
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/PackageOperationResponse"
    """
    # TODO: Use `uv remove` instead of package manager uninstall for better dependency management
    body = await parse_request(request, cls=RemovePackageRequest)

    package_manager = _get_package_manager(request)
    if not package_manager.is_manager_installed():
        package_manager.alert_not_installed()
        return PackageOperationResponse.of_failure(
            f"{package_manager.name} is not available. "
            f"Check out the docs for installation instructions: {package_manager.docs_url}"
        )

    group = body.group or None
    output_lines: list[str] = []
    success = await package_manager.uninstall(
        body.package, group=group, log_callback=output_lines.append
    )

    # Update the script metadata
    filename = _get_filename(request)
    if filename is not None and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        await asyncio.to_thread(
            package_manager.update_notebook_script_metadata,
            filepath=filename,
            packages_to_remove=split_packages(body.package),
            upgrade=False,
        )

    if success:
        return PackageOperationResponse.of_success()

    return PackageOperationResponse.of_failure(
        _format_install_error(
            "".join(output_lines),
            fallback=(
                f"Failed to uninstall {body.package}. "
                "See terminal for error logs."
            ),
        )
    )


@router.get("/list")
@requires("edit")
async def list_packages(request: Request) -> ListPackagesResponse:
    """
    responses:
        200:
            description: List installed packages
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/ListPackagesResponse"
    """
    package_manager = _get_package_manager(request)
    if not package_manager.is_manager_installed():
        package_manager.alert_not_installed()
        return ListPackagesResponse(packages=[])

    packages = await asyncio.to_thread(package_manager.list_packages)

    return ListPackagesResponse(packages=packages)


@router.get("/tree")
@requires("edit")
async def dependency_tree(request: Request) -> DependencyTreeResponse:
    """
    responses:
        200:
            description: List dependency tree
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/DependencyTreeResponse"
    """
    package_manager = _get_package_manager(request)

    filename = _get_filename(request)
    # TODO(manzt): Same as check below when installing packages. If we are
    # managing script metadata, we are in sandbox mode.
    is_sandbox = (
        filename is not None and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA
    )
    if is_sandbox:
        tree = await asyncio.to_thread(
            package_manager.dependency_tree, filename
        )
    else:
        tree = await asyncio.to_thread(package_manager.dependency_tree)
    return DependencyTreeResponse(tree=tree)


def _get_package_manager(request: Request) -> PackageManager:
    session = AppState(request).get_current_session()
    if not session:
        return create_package_manager(
            AppState(request).config_manager.package_manager
        )

    config_manager = AppState(request).app_config_manager

    # Check if IPC mode - use kernel's venv Python
    python_exe: str | None = None
    from marimo._session.managers.ipc import IPCKernelManagerImpl
    from marimo._session.session import SessionImpl

    if isinstance(session, SessionImpl):
        kernel_manager = session._kernel_manager
        if isinstance(kernel_manager, IPCKernelManagerImpl):
            python_exe = kernel_manager.venv_python

    return create_package_manager(
        config_manager.package_manager, python_exe=python_exe
    )


def _get_filename(request: Request) -> str | None:
    session = AppState(request).get_current_session()
    if session is None:
        return None
    return session.app_file_manager.filename
