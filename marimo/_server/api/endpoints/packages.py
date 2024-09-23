# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

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
    success = await package_manager.install(body.package, version=None)
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
    success = await package_manager.uninstall(body.package)
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
    packages = package_manager.list_packages()

    return ListPackagesResponse(packages=packages)


def _get_package_manager(request: Request) -> PackageManager:
    config_manager = AppState(request).config_manager
    return create_package_manager(
        config_manager.get_config()["package_management"]["manager"]
    )
