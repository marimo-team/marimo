# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._environments import script_metadata
from marimo._environments.backends import current_backend
from marimo._environments.errors import (
    EnvironmentManagerError,
    SandboxRestartRequired,
)
from marimo._environments.sandbox import Backend, NotebookSandbox
from marimo._runtime.packages.package_manager import PackageManager
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.sandbox_package_manager import (
    SandboxPackageManager,
)
from marimo._runtime.packages.utils import split_packages
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.packages import (
    AddPackageRequest,
    DependencyTreeResponse,
    ListPackagesResponse,
    PackageInstallationContext,
    PackageManagerContext,
    PackageOperationResponse,
    RemovePackageRequest,
    SandboxPackageContext,
    SandboxRequest,
    SandboxResponse,
    SyncSandboxResponse,
    UpdateManifestRequest,
)
from marimo._server.router import APIRouter
from marimo._utils.http import HTTPException

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for packages endpoints
router = APIRouter()


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

    package_manager = _get_package_manager(request)
    if not package_manager.is_manager_installed():
        package_manager.alert_not_installed()
        return PackageOperationResponse.of_failure(
            f"{package_manager.name} is not available. "
            f"Check out the docs for installation instructions: {package_manager.docs_url}"
        )

    upgrade = body.upgrade or False
    group = body.group or None
    success = await package_manager.install(
        body.package, version=None, upgrade=upgrade, group=group
    )

    # Update the script metadata
    filename = _get_filename(request)
    if (
        success
        and filename is not None
        and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA
    ):
        await asyncio.to_thread(
            package_manager.update_notebook_script_metadata,
            filepath=filename,
            packages_to_add=split_packages(body.package),
            upgrade=upgrade,
        )

    if success:
        return PackageOperationResponse.of_success()

    if package_manager.restart_required:
        return PackageOperationResponse(success=False, restart_required=True)

    return PackageOperationResponse.of_failure(
        _failure_message(package_manager)
        or f"Failed to install {body.package}. See terminal for error logs."
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
    success = await package_manager.uninstall(body.package, group=group)

    # Update the script metadata
    filename = _get_filename(request)
    if (
        success
        and filename is not None
        and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA
    ):
        await asyncio.to_thread(
            package_manager.update_notebook_script_metadata,
            filepath=filename,
            packages_to_remove=split_packages(body.package),
            upgrade=False,
        )

    if success:
        return PackageOperationResponse.of_success()

    if package_manager.restart_required:
        return PackageOperationResponse(success=False, restart_required=True)

    return PackageOperationResponse.of_failure(
        _failure_message(package_manager)
        or f"Failed to uninstall {body.package}. See terminal for error logs."
    )


def _failure_message(package_manager: PackageManager) -> str | None:
    if isinstance(package_manager, SandboxPackageManager):
        return package_manager.last_error
    return None


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
    context = _get_package_installation_context(package_manager)

    filename = _get_filename(request)
    is_sandbox = (
        filename is not None and GLOBAL_SETTINGS.SANDBOX_MODE is not None
    )
    if is_sandbox:
        tree = await asyncio.to_thread(
            package_manager.dependency_tree, filename
        )
    else:
        tree = await asyncio.to_thread(package_manager.dependency_tree)
    return DependencyTreeResponse(tree=tree, context=context)


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
        sandbox = session.notebook_sandbox
        if isinstance(sandbox, NotebookSandbox):
            return SandboxPackageManager(sandbox)

        kernel_manager = session._kernel_manager
        if isinstance(kernel_manager, IPCKernelManagerImpl):
            python_exe = kernel_manager.venv_python

    return create_package_manager(
        config_manager.package_manager,
        python_exe=python_exe,
    )


def _get_package_installation_context(
    package_manager: PackageManager,
) -> PackageInstallationContext:
    if isinstance(package_manager, SandboxPackageManager):
        return SandboxPackageContext(backend=package_manager.backend)
    return PackageManagerContext(name=package_manager.name)


def _get_filename(request: Request) -> str | None:
    session = AppState(request).get_current_session()
    if session is None:
        return None
    return session.app_file_manager.filename


def _sandbox_source(
    request: Request, file_key: str | None, *, mutation: bool = False
) -> tuple[NotebookSandbox | None, str | None, Backend | None]:
    state = AppState(request)
    manager = state.session_manager
    if mutation and manager.is_session_starting(
        state.require_current_session_id()
    ):
        raise HTTPException(409, "Wait for sandbox preparation to finish.")
    session = state.get_current_session()
    if session is not None:
        sandbox = getattr(session, "notebook_sandbox", None)
        if isinstance(sandbox, NotebookSandbox):
            return sandbox, sandbox.source, sandbox.backend
        return None, None, None
    if not manager.sandbox:
        return None, None, None
    key = file_key or manager.workspace.get_unique_file_key()
    path = manager.workspace.resolve(key) if key else None
    return None, path, current_backend()


@router.post("/sandbox")
@requires("edit")
async def get_sandbox(request: Request) -> SandboxResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SandboxRequest"
    responses:
        200:
            description: Sandbox manifest, available before kernel startup
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SandboxResponse"
    """
    body = await parse_request(request, cls=SandboxRequest)
    _, path, backend = _sandbox_source(request, body.file_key)
    manifest = (
        await asyncio.to_thread(script_metadata.read_manifest, path)
        if path is not None
        else None
    )
    return SandboxResponse(backend=backend, manifest=manifest, filename=path)


@router.post("/manifest")
@requires("edit")
async def update_manifest(request: Request) -> SandboxResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/UpdateManifestRequest"
    responses:
        200:
            description: Save notebook metadata without changing its cells
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SandboxResponse"
    """
    body = await parse_request(request, cls=UpdateManifestRequest)
    _, path, backend = _sandbox_source(request, body.file_key, mutation=True)
    if path is None or backend is None:
        raise HTTPException(400, "No notebook manifest is available to edit.")
    try:
        manifest = await asyncio.to_thread(
            script_metadata.write_manifest,
            path,
            body.contents,
            previous=body.previous,
        )
    except script_metadata.ManifestConflictError as error:
        raise HTTPException(409, str(error)) from error
    except (ValueError, EnvironmentManagerError) as error:
        raise HTTPException(400, str(error)) from error
    return SandboxResponse(backend=backend, manifest=manifest, filename=path)


@router.post("/sync")
@requires("edit")
async def sync_sandbox(request: Request) -> SyncSandboxResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SandboxRequest"
    responses:
        200:
            description: Apply the saved manifest, or reconnect to retry startup
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SyncSandboxResponse"
    """
    body = await parse_request(request, cls=SandboxRequest)
    sandbox, _, backend = _sandbox_source(
        request, body.file_key, mutation=True
    )
    if backend is None:
        raise HTTPException(400, "This notebook does not use a sandbox.")
    if sandbox is None:
        # Connection creation owns provisioning and streams its progress.
        return SyncSandboxResponse(success=True, reconnect=True)
    try:
        await sandbox.sync_async()
    except SandboxRestartRequired as error:
        return SyncSandboxResponse(
            success=False, error=str(error), restart_required=True
        )
    except (EnvironmentManagerError, OSError) as error:
        return SyncSandboxResponse(success=False, error=str(error))
    return SyncSandboxResponse(success=True)
