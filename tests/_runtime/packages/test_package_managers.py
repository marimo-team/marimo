import pytest

from marimo._runtime.packages.package_managers import create_package_manager
from marimo._runtime.packages.pypi_package_manager import (
    MicropipPackageManager,
    PipPackageManager,
    RyePackageManager,
    UvPackageManager,
)


def test_create_package_managers() -> None:
    assert isinstance(create_package_manager("pip"), PipPackageManager)
    assert isinstance(
        create_package_manager("micropip"), MicropipPackageManager
    )
    assert isinstance(create_package_manager("rye"), RyePackageManager)
    assert isinstance(create_package_manager("uv"), UvPackageManager)

    with pytest.raises(RuntimeError) as e:
        create_package_manager("foobar")
    assert "Unknown package manager" in str(e)
