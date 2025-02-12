from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar
from unittest.mock import patch

from marimo._config.config import PartialMarimoConfig, merge_default_config
from marimo._config.manager import (
    MarimoConfigManager,
    MarimoConfigReaderWithOverrides,
    UserConfigManager,
    get_default_config_manager,
)

F = TypeVar("F", bound=Callable[..., Any])


def restore_config(f: F) -> F:
    config = UserConfigManager().get_config()

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        finally:
            UserConfigManager().save_config(config)

    return wrapper  # type: ignore


@restore_config
@patch("tomlkit.dump")
def test_save_config(mock_dump: Any) -> None:
    mock_config = merge_default_config(PartialMarimoConfig())
    manager = UserConfigManager()
    manager._load_config = lambda: mock_config

    result = manager.save_config(mock_config)

    assert result == mock_config

    assert mock_dump.mock_calls[0][1][0] == mock_config


@restore_config
@patch("tomlkit.dump")
def test_can_save_secrets(mock_dump: Any) -> None:
    mock_config = merge_default_config(PartialMarimoConfig())
    manager = UserConfigManager()
    manager._load_config = lambda: mock_config

    new_config = manager.save_config(
        merge_default_config(
            PartialMarimoConfig(ai={"open_ai": {"api_key": "super_secret"}})
        )
    )
    manager._load_config = lambda: new_config

    assert (
        mock_dump.mock_calls[0][1][0]["ai"]["open_ai"]["api_key"]
        == "super_secret"
    )

    # Do not overwrite secrets
    manager.save_config(
        merge_default_config(
            PartialMarimoConfig(ai={"open_ai": {"api_key": "********"}})
        )
    )
    assert (
        mock_dump.mock_calls[1][1][0]["ai"]["open_ai"]["api_key"]
        == "super_secret"
    )


@restore_config
def test_can_read_secrets() -> None:
    manager = UserConfigManager()
    mock_config = merge_default_config(
        PartialMarimoConfig(ai={"open_ai": {"api_key": "super_secret"}})
    )
    manager._load_config = lambda: mock_config

    assert manager.get_config()["ai"]["open_ai"]["api_key"] == "********"
    assert (
        manager.get_config(hide_secrets=False)["ai"]["open_ai"]["api_key"]
        == "super_secret"
    )


@restore_config
def test_get_config() -> None:
    mock_config = merge_default_config(PartialMarimoConfig())
    manager = UserConfigManager()
    manager._load_config = lambda: mock_config

    result = manager.get_config()

    assert result == mock_config


@restore_config
def test_get_config_with_override() -> None:
    mock_config = merge_default_config(PartialMarimoConfig())
    user = UserConfigManager()
    user._load_config = lambda: mock_config

    manager = MarimoConfigManager(
        user,
        MarimoConfigReaderWithOverrides(
            {
                "runtime": {
                    "on_cell_change": "autorun",
                    "auto_instantiate": True,
                    "auto_reload": "lazy",
                    "watcher_on_save": "lazy",
                }
            }
        ),
    )
    assert manager.get_config()["runtime"]["auto_reload"] == "lazy"

    manager = get_default_config_manager(current_path=None).with_overrides(
        {
            "runtime": {
                "on_cell_change": "autorun",
                "auto_instantiate": True,
                "auto_reload": "lazy",
                "watcher_on_save": "lazy",
            }
        }
    )
    assert manager.get_config()["runtime"]["auto_reload"] == "lazy"
