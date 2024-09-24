# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from marimo._runtime.packages.package_manager import PackageDescription


@dataclass
class AddPackageRequest:
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


@dataclass
class RemovePackageRequest:
    package: str


@dataclass
class ListPackagesResponse:
    packages: List[PackageDescription]


@dataclass
class PackageOperationResponse:
    success: bool
    error: Optional[str] = None

    @staticmethod
    def of_success() -> PackageOperationResponse:
        return PackageOperationResponse(success=True, error=None)

    @staticmethod
    def of_failure(error: str) -> PackageOperationResponse:
        return PackageOperationResponse(success=False, error=error)
