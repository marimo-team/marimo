# Copyright 2026 Marimo. All rights reserved.
"""Tests for URL parameter mapping and extraction."""

from __future__ import annotations

from marimo._server.app_defaults import AppDefaults
from marimo._server.url_params import (
    INTERNAL_URL_PARAM_KEYS,
    URL_PARAM_MAPPINGS,
    build_header_from_params,
)


class TestURLParamMappings:
    def test_venv_mapping_exists(self) -> None:
        assert "venv" in URL_PARAM_MAPPINGS
        mapping = URL_PARAM_MAPPINGS["venv"]
        assert mapping.url_key == "venv"
        assert mapping.config_path == ("tool", "marimo", "env", "venv")

    def test_internal_keys_include_venv(self) -> None:
        assert "venv" in INTERNAL_URL_PARAM_KEYS


class TestBuildHeaderFromParams:
    def test_empty_params_returns_none(self) -> None:
        result = build_header_from_params({})
        assert result is None

    def test_unknown_params_returns_none(self) -> None:
        result = build_header_from_params({"unknown": "value"})
        assert result is None

    def test_venv_param_builds_header(self) -> None:
        result = build_header_from_params({"venv": "/path/to/venv"})
        assert result is not None
        assert "# /// script" in result
        assert "# ///" in result
        assert "[tool.marimo.env]" in result
        assert 'venv = "/path/to/venv"' in result

    def test_multiple_params_builds_header(self) -> None:
        # Once we add more params, this test can verify they all work
        result = build_header_from_params({"venv": "/my/venv"})
        assert result is not None
        assert "venv" in result


class TestAppDefaultsFromURLParams:
    def test_empty_params_returns_base_with_no_header(self) -> None:
        base = AppDefaults(width="full", sql_output="polars")
        result = AppDefaults.from_url_params(base, {})
        assert result.width == "full"
        assert result.sql_output == "polars"
        assert result.header is None

    def test_venv_param_sets_header(self) -> None:
        base = AppDefaults()
        result = AppDefaults.from_url_params(base, {"venv": "/path/to/venv"})
        assert result.header is not None
        assert "[tool.marimo.env]" in result.header
        assert 'venv = "/path/to/venv"' in result.header

    def test_preserves_base_defaults(self) -> None:
        base = AppDefaults(
            width="compact",
            sql_output="pandas",
            auto_download=["html"],
        )
        result = AppDefaults.from_url_params(base, {"venv": "/venv"})
        assert result.width == "compact"
        assert result.sql_output == "pandas"
        assert result.auto_download == ["html"]
        assert result.header is not None

    def test_unknown_params_ignored(self) -> None:
        base = AppDefaults()
        result = AppDefaults.from_url_params(base, {"unknown": "value"})
        # Should not raise, unknown params are ignored
        assert result.header is None


class TestAppFileManagerWithHeader:
    """Tests for AppFileManager integration with URL param headers."""

    def test_new_notebook_has_header_set(self) -> None:
        """Test that AppFileManager sets header on new notebooks."""
        from marimo._session.notebook import AppFileManager

        header = (
            '# /// script\n# [tool.marimo.env]\n# venv = "/my/venv"\n# ///'
        )
        defaults = AppDefaults(header=header)
        manager = AppFileManager(filename=None, defaults=defaults)
        assert manager.app._app._header == header

    def test_to_code_includes_header(self) -> None:
        """Test that to_code() includes the PEP 723 header."""
        from marimo._session.notebook import AppFileManager

        header = build_header_from_params({"venv": "/path/to/venv"})
        defaults = AppDefaults(header=header)
        manager = AppFileManager(filename=None, defaults=defaults)

        code = manager.to_code()
        assert "# /// script" in code
        assert "[tool.marimo.env]" in code
        assert 'venv = "/path/to/venv"' in code

    def test_end_to_end_url_params_to_header(self) -> None:
        """Test complete flow from URL params to header in code."""
        from marimo._session.notebook import AppFileManager

        base_defaults = AppDefaults(width="full")
        url_params = {"venv": "/my/project/.venv"}
        defaults = AppDefaults.from_url_params(base_defaults, url_params)

        manager = AppFileManager(filename=None, defaults=defaults)
        code = manager.to_code()

        # Header should be present
        assert "# /// script" in code
        assert "[tool.marimo.env]" in code
        assert 'venv = "/my/project/.venv"' in code

        # Width should still be applied
        assert manager.app.config.width == "full"
