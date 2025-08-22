# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from marimo._utils.config.config import ConfigReader

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class TestConfig:
    __test__ = False
    value: str
    nullable_value: Optional[str] = None


def test_read_toml_invalid_syntax(tmp_path: Path) -> None:
    (tmp_path / "invalid.toml").write_text("key = 'value',")

    reader = ConfigReader(tmp_path / "invalid.toml")
    fallback = TestConfig(value="fallback")
    result = reader.read_toml(TestConfig, fallback=fallback)
    assert result == fallback


def test_read_toml_valid(tmp_path: Path) -> None:
    (tmp_path / "valid.toml").write_text('value = "test"')

    reader = ConfigReader(tmp_path / "valid.toml")
    fallback = TestConfig(value="fallback")
    result = reader.read_toml(TestConfig, fallback=fallback)
    assert result == TestConfig(value="test")


def test_write_toml_valid(tmp_path: Path) -> None:
    config = ConfigReader(tmp_path / "valid.toml")
    written = TestConfig(value="test", nullable_value="value")
    config.write_toml(written)

    fallback = TestConfig(value="fallback")
    result = config.read_toml(TestConfig, fallback=fallback)
    assert result == written


def test_write_toml_invalid_values(tmp_path: Path) -> None:
    config = ConfigReader(tmp_path / "invalid.toml")
    # None is not valid toml
    config.write_toml(TestConfig(value="test", nullable_value=None))

    fallback = TestConfig(value="fallback")
    result = config.read_toml(TestConfig, fallback=fallback)
    assert result == TestConfig(value="test")
