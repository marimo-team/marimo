# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

import msgspec

from marimo._runtime.packages.package_manager import PackageDescription


class AddPackageRequest(msgspec.Struct, rename="camel"):
    """
    This can be a remove package or a local package.

    Supported formats:

    httpx
    httpx==0.27.0
    httpx>=0.27.0
    git+https://github.com/encode/httpx
    https://files.pythonhosted.org/packages/5c/2d/3da5bdf4408b8b2800061c339f240c1802f2e82d55e50bd39c5a881f47f0/httpx-0.27.0.tar.gz
    /example/foo-0.1.0-py3-none-any.whl
    """

    package: str
    upgrade: Optional[bool] = False


class RemovePackageRequest(msgspec.Struct, rename="camel"):
    package: str


class ListPackagesResponse(msgspec.Struct, rename="camel"):
    packages: list[PackageDescription]


class DependencyTreeNode(msgspec.Struct, rename="camel"):
    name: str
    version: Optional[str]
    # List of {"kind": "extra"|"group", "value": str}
    tags: list[dict[str, str]]
    dependencies: list[DependencyTreeNode]


class DependencyTreeResponse(msgspec.Struct, rename="camel"):
    tree: Optional[DependencyTreeNode]


class PackageOperationResponse(msgspec.Struct, rename="camel"):
    success: bool
    error: Optional[str] = None

    @staticmethod
    def of_success() -> PackageOperationResponse:
        return PackageOperationResponse(success=True, error=None)

    @staticmethod
    def of_failure(error: str) -> PackageOperationResponse:
        return PackageOperationResponse(success=False, error=error)
