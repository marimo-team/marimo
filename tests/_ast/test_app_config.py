from __future__ import annotations

from typing import Any

import pytest

from marimo._ast.app_config import _AppConfig


def test_app_config_default():
    config = _AppConfig()
    assert config.width == "compact"
    assert config.app_title is None
    assert config.css_file is None
    assert config.html_head_file is None
    assert config.auto_download == []
    assert config.sql_output == "auto"


def test_app_config_from_untrusted_dict():
    updates = {
        "width": "full",
        "app_title": "My App",
        "css_file": "custom.css",
        "html_head_file": "head.html",
        "auto_download": ["html", "markdown"],
        "invalid_key": "should be ignored",
        "sql_output": "polars",
    }
    config = _AppConfig.from_untrusted_dict(updates)
    assert config.width == "full"
    assert config.app_title == "My App"
    assert config.css_file == "custom.css"
    assert config.html_head_file == "head.html"
    assert config.auto_download == ["html", "markdown"]
    assert config.sql_output == "polars"
    assert not hasattr(config, "invalid_key")


def test_app_config_asdict():
    config = _AppConfig(
        width="medium",
        app_title="Test App",
        css_file="style.css",
        html_head_file="head.html",
        auto_download=["html"],
        sql_output="lazy-polars",
    )
    config_dict = config.asdict()
    assert config_dict == {
        "width": "medium",
        "app_title": "Test App",
        "css_file": "style.css",
        "html_head_file": "head.html",
        "auto_download": ["html"],
        "layout_file": None,
        "sql_output": "lazy-polars",
    }


def test_app_config_update():
    config = _AppConfig()
    assert config.width == "compact"
    assert config.app_title is None
    assert config.sql_output == "auto"

    updated_config = config.update(
        {
            "width": "full",
            "app_title": "Test App",
            "sql_output": "lazy-polars",
        }
    )
    assert updated_config.width == "full"
    assert updated_config.app_title == "Test App"
    assert updated_config.sql_output == "lazy-polars"

    # Test updating a single field
    updated_config = config.update({"app_title": "Updated App"})
    assert updated_config.width == "full"
    assert updated_config.app_title == "Updated App"
    assert updated_config.sql_output == "lazy-polars"


@pytest.mark.parametrize(
    ("auto_download", "expected"),
    [
        ([], []),
        (["html"], ["html"]),
        (["markdown"], ["markdown"]),
        (["html", "markdown"], ["html", "markdown"]),
        # Invalid values should be left
        # so it forwards-compatible
        (["invalid"], ["invalid"]),
    ],
)
def test_app_config_auto_download(
    auto_download: list[Any], expected: list[str]
) -> None:
    config = _AppConfig(auto_download=auto_download)
    assert config.auto_download == expected
