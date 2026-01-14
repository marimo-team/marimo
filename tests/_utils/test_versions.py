# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._utils.versions import (
    extract_extras,
    has_version_specifier,
    without_extras,
    without_version_specifier,
)


class TestWithoutVersionSpecifier:
    """Tests for without_version_specifier function"""

    def test_removes_version_specifiers(self) -> None:
        # Test various version specifier operators
        assert without_version_specifier("numpy==1.24.0") == "numpy"
        assert without_version_specifier("pandas>1.5.0") == "pandas"
        assert without_version_specifier("scipy>=1.10.0") == "scipy"
        assert without_version_specifier("requests<3.0.0") == "requests"
        assert without_version_specifier("urllib3<=2.0.0") == "urllib3"
        assert without_version_specifier("flask~=2.0.0") == "flask"
        # Exclusion operator (PEP 440)
        assert without_version_specifier("package!=1.0.0") == "package"

    def test_handles_whitespace(self) -> None:
        # Whitespace around version operators should be stripped
        assert without_version_specifier("package >= 1.0.0") == "package"
        assert without_version_specifier("package >=1.0.0") == "package"

    def test_preserves_package_without_version(self) -> None:
        assert without_version_specifier("django") == "django"
        assert without_version_specifier("") == ""

    def test_handles_extras_and_special_chars(self) -> None:
        # Should remove version but keep extras
        assert (
            without_version_specifier("requests[security]>=2.0.0")
            == "requests[security]"
        )
        # Only splits on first specifier
        assert without_version_specifier("package>=1.0.0,<2.0.0") == "package"
        # Handles hyphens and underscores
        assert (
            without_version_specifier("scikit-learn>=1.0.0") == "scikit-learn"
        )
        assert (
            without_version_specifier("typing_extensions>=4.0.0")
            == "typing_extensions"
        )


class TestWithoutExtras:
    """Tests for without_extras function"""

    def test_removes_extras(self) -> None:
        # Single extra
        assert without_extras("requests[security]") == "requests"
        # Multiple extras
        assert without_extras("requests[security,socks]") == "requests"
        # Nested brackets (splits at first bracket)
        assert without_extras("package[extra[nested]]") == "package"

    def test_preserves_package_without_extras(self) -> None:
        assert without_extras("numpy") == "numpy"
        assert without_extras("") == ""

    def test_handles_extras_with_versions_and_special_chars(self) -> None:
        # Removes extras and anything after them (including version specifiers)
        assert without_extras("requests[security]>=2.0.0") == "requests"
        # Handles hyphens and underscores
        assert without_extras("scikit-learn[all]") == "scikit-learn"
        assert without_extras("typing_extensions[test]") == "typing_extensions"


class TestExtractExtras:
    """Tests for extract_extras function"""

    def test_extracts_single_extra(self) -> None:
        assert extract_extras("requests[security]") == "[security]"

    def test_extracts_multiple_extras(self) -> None:
        assert extract_extras("requests[security,socks]") == "[security,socks]"

    def test_no_extras(self) -> None:
        assert extract_extras("numpy") == ""
        assert extract_extras("") == ""

    def test_extras_with_version_specifier(self) -> None:
        # extract_extras expects version specifier to be removed first
        package = "requests[security]>=2.0.0"
        assert (
            extract_extras(without_version_specifier(package)) == "[security]"
        )

    def test_extras_with_nested_brackets(self) -> None:
        # Should include everything after the first opening bracket
        assert extract_extras("package[extra[nested]]") == "[extra[nested]]"

    def test_extras_with_special_chars(self) -> None:
        assert extract_extras("package[a-b_c.d]") == "[a-b_c.d]"


class TestHasVersionSpecifier:
    """Tests for has_version_specifier function"""

    def test_detects_version_specifiers(self) -> None:
        # Various operators
        assert has_version_specifier("numpy==1.24.0") is True
        assert has_version_specifier("pandas>1.5.0") is True
        assert has_version_specifier("scipy>=1.10.0") is True
        assert has_version_specifier("requests<3.0.0") is True
        assert has_version_specifier("urllib3<=2.0.0") is True
        assert has_version_specifier("flask~=2.0.0") is True
        # Exclusion operator (PEP 440)
        assert has_version_specifier("package!=1.0.0") is True
        # Multiple specifiers
        assert has_version_specifier("package>=1.0.0,<2.0.0") is True

    def test_detects_no_version_specifier(self) -> None:
        assert has_version_specifier("django") is False
        assert has_version_specifier("") is False
        # Extras without version
        assert has_version_specifier("requests[security]") is False
        # Hyphens and underscores are not version specifiers
        assert has_version_specifier("scikit-learn") is False
        assert has_version_specifier("typing_extensions") is False

    def test_handles_extras_with_version(self) -> None:
        assert has_version_specifier("requests[security]>=2.0.0") is True


class TestCombinedUsage:
    """Tests for combined usage of utility functions"""

    def test_chaining_functions(self) -> None:
        package = "requests[security]>=2.0.0"
        # Chain extras -> version
        assert without_version_specifier(without_extras(package)) == "requests"
        # Chain version -> extras
        assert without_extras(without_version_specifier(package)) == "requests"

    @pytest.mark.parametrize(
        ("package", "expected_name"),
        [
            ("numpy==1.24.0", "numpy"),
            ("pandas[all]>=1.5.0", "pandas"),
            ("scikit-learn", "scikit-learn"),
            ("requests[security,socks]<3.0.0", "requests"),
            ("typing_extensions>=4.0.0", "typing_extensions"),
        ],
    )
    def test_extract_clean_package_name(
        self, package: str, expected_name: str
    ) -> None:
        """Test extracting clean package name from various formats"""
        result = without_extras(without_version_specifier(package))
        assert result == expected_name
