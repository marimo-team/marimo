# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

import msgspec

from marimo._runtime.packages.package_manager import PackageDescription
from marimo._utils.uv_tree import DependencyTreeNode


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
    group: Optional[str] = None


class RemovePackageRequest(msgspec.Struct, rename="camel"):
    package: str
    group: Optional[str] = None


class ListPackagesResponse(msgspec.Struct, rename="camel"):
    packages: list[PackageDescription]


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
