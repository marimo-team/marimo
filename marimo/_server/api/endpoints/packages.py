# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from starlette.authentication import requires

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._runtime.packages.package_manager import PackageManager
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.packages import (
    AddPackageRequest,
    ListPackagesResponse,
    PackageOperationResponse,
    RemovePackageRequest,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for packages endpoints
router = APIRouter()


@router.post("/add")
@requires("edit")
async def install_package(request: Request) -> PackageOperationResponse:
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
            f"Check out the docs for installation instructions: {package_manager.docs_url}"  # noqa: E501
        )

    success = await package_manager.install(body.package, version=None)

    # Update the script metadata
    filename = _get_filename(request)
    if filename is not None and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        package_manager.update_notebook_script_metadata(
            filepath=filename,
            import_namespaces_to_add=[body.package],
            import_namespaces_to_remove=[],
        )

    if success:
        return PackageOperationResponse.of_success()

    return PackageOperationResponse.of_failure(
        f"Failed to install {body.package}. See terminal for error logs."
    )


@router.post("/remove")
@requires("edit")
async def uninstall_package(request: Request) -> PackageOperationResponse:
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
    body = await parse_request(request, cls=RemovePackageRequest)

    package_manager = _get_package_manager(request)
    if not package_manager.is_manager_installed():
        package_manager.alert_not_installed()
        return PackageOperationResponse.of_failure(
            f"{package_manager.name} is not available. "
            f"Check out the docs for installation instructions: {package_manager.docs_url}"  # noqa: E501
        )

    success = await package_manager.uninstall(body.package)

    # Update the script metadata
    filename = _get_filename(request)
    if filename is not None and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        package_manager.update_notebook_script_metadata(
            filepath=filename,
            import_namespaces_to_add=[],
            import_namespaces_to_remove=[body.package],
        )

    if success:
        return PackageOperationResponse.of_success()

    return PackageOperationResponse.of_failure(
        f"Failed to uninstall {body.package}. See terminal for error logs."
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

    packages = package_manager.list_packages()

    return ListPackagesResponse(packages=packages)


def _get_package_manager(request: Request) -> PackageManager:
    config_manager = AppState(request).config_manager
    return create_package_manager(
        config_manager.get_config()["package_management"]["manager"]
    )


def _get_filename(request: Request) -> Optional[str]:
    session = AppState(request).get_current_session()
    if session is None:
        return None
    return session.app_file_manager.filename
