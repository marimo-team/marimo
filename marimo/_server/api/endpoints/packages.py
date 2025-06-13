# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from starlette.authentication import requires

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._runtime.packages.package_manager import PackageManager
from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.utils import split_packages
from marimo._server.api.dependency_tree import get_dependency_tree
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
            f"Check out the docs for installation instructions: {package_manager.docs_url}"  # noqa: E501
        )

    upgrade = body.upgrade or False
    success = await package_manager.install(
        body.package, version=None, upgrade=upgrade
    )

    # Update the script metadata
    filename = _get_filename(request)
    if filename is not None and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        package_manager.update_notebook_script_metadata(
            filepath=filename,
            packages_to_add=split_packages(body.package),
            upgrade=upgrade,
        )

    if success:
        return PackageOperationResponse.of_success()

    return PackageOperationResponse.of_failure(
        f"Failed to install {body.package}. See terminal for error logs."
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
            f"Check out the docs for installation instructions: {package_manager.docs_url}"  # noqa: E501
        )

    success = await package_manager.uninstall(body.package)

    # Update the script metadata
    filename = _get_filename(request)
    if filename is not None and GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        package_manager.update_notebook_script_metadata(
            filepath=filename,
            packages_to_remove=split_packages(body.package),
            upgrade=False,
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
    filename = _get_filename(request)
    assert filename, "`uv tree` only supported for --sandbox"

    return DependencyTreeResponse(tree=get_dependency_tree(filename))


def _get_package_manager(request: Request) -> PackageManager:
    if not AppState(request).get_current_session():
        return create_package_manager(
            AppState(request).config_manager.package_manager
        )

    config_manager = AppState(request).app_config_manager
    return create_package_manager(config_manager.package_manager)


def _get_filename(request: Request) -> Optional[str]:
    session = AppState(request).get_current_session()
    if session is None:
        return None
    return session.app_file_manager.filename
