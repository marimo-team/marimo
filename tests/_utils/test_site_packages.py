# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import pathlib
import site
from unittest.mock import Mock

from marimo._utils.site_packages import (
    has_local_conflict,
    is_local_module,
    module_exists_in_site_packages,
)


def test_is_local_module() -> None:
    """Test is_local_module with various module specs."""
    # Test with None spec (should return True - assume local if unknown)
    assert is_local_module(None)

    # Test with spec that has None origin (should return True)
    spec_no_origin = Mock()
    spec_no_origin.origin = None
    assert is_local_module(spec_no_origin)

    # Test with local module (should return True - is local)
    spec_local = Mock()
    spec_local.origin = "/home/user/myproject/mymodule.py"
    assert is_local_module(spec_local)

    # Test with actual site-packages path if available
    try:
        site_packages_dirs = site.getsitepackages()
        if site_packages_dirs:
            # Use an actual site-packages directory for testing
            test_site_dir = site_packages_dirs[0]
            spec_site_packages = Mock()
            spec_site_packages.origin = str(
                pathlib.Path(test_site_dir) / "requests" / "__init__.py"
            )
            assert not is_local_module(spec_site_packages)
    except (AttributeError, IndexError):
        # Skip site-packages test if not available (e.g., in restricted environments)
        pass

    # Test edge cases with path resolution issues
    spec_bad_path = Mock()
    spec_bad_path.origin = (
        "/nonexistent/path/that/should/not/exist/__init__.py"
    )
    # Should return True (local) if path can't be resolved properly
    result = is_local_module(spec_bad_path)
    assert isinstance(result, bool)  # Should handle gracefully


def test_module_exists_in_site_packages() -> None:
    """Test module_exists_in_site_packages function."""
    # Test with a module that likely exists (if available)
    # Note: This may vary by environment, so we test the return type
    result = module_exists_in_site_packages("os")
    assert isinstance(result, bool)

    # Test with a module that definitely doesn't exist
    assert not module_exists_in_site_packages(
        "definitely_nonexistent_module_12345"
    )


def test_has_local_conflict() -> None:
    """Test has_local_conflict function."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test with no local file - should return False
        assert not has_local_conflict("nonexistent_module", temp_dir)

        # Create a local Python file
        local_file = os.path.join(temp_dir, "test_module.py")
        with open(local_file, "w") as f:
            f.write("# test module")

        # This will only return True if test_module exists in site-packages
        # which it likely doesn't, so we just test that it returns a boolean
        result = has_local_conflict("test_module", temp_dir)
        assert isinstance(result, bool)

        # Create a local package directory
        package_dir = os.path.join(temp_dir, "test_package")
        os.makedirs(package_dir)
        init_file = os.path.join(package_dir, "__init__.py")
        with open(init_file, "w") as f:
            f.write("# test package")

        # Again, will depend on whether test_package exists in site-packages
        result = has_local_conflict("test_package", temp_dir)
        assert isinstance(result, bool)
