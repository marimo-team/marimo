from __future__ import annotations

from typing import Any

import pytest

from marimo._ast.app import _AppConfig


def test_app_config_default():
    config = _AppConfig()
    assert config.width == "compact"
    assert config.app_title is None
    assert config.css_file is None
    assert config.auto_download == []


def test_app_config_from_untrusted_dict():
    updates = {
        "width": "full",
        "app_title": "My App",
        "css_file": "custom.css",
        "auto_download": ["html", "markdown"],
        "invalid_key": "should be ignored",
    }
    config = _AppConfig.from_untrusted_dict(updates)
    assert config.width == "full"
    assert config.app_title == "My App"
    assert config.css_file == "custom.css"
    assert config.auto_download == ["html", "markdown"]
    assert not hasattr(config, "invalid_key")


def test_app_config_asdict():
    config = _AppConfig(
        width="medium",
        app_title="Test App",
        css_file="style.css",
        auto_download=["html"],
    )
    config_dict = config.asdict()
    assert config_dict == {
        "width": "medium",
        "app_title": "Test App",
        "css_file": "style.css",
        "auto_download": ["html"],
        "layout_file": None,
    }


def test_app_config_update():
    config = _AppConfig()
    updates = {
        "width": "full",
        "app_title": "Updated App",
        "auto_download": ["markdown"],
    }
    updated_config = config.update(updates)
    assert updated_config.width == "full"
    assert updated_config.app_title == "Updated App"
    assert updated_config.auto_download == ["markdown"]
    assert updated_config.css_file is None


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
