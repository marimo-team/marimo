# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from tempfile import NamedTemporaryFile

from marimo._utils.config.config import ConfigReader


@dataclass
class TestConfig:
    __test__ = False
    value: str


def test_read_toml_invalid_syntax() -> None:
    with NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        # Write invalid TOML content (missing value after comma)
        f.write("key = 'value',")
        f.flush()

        reader = ConfigReader(f.name)
        fallback = TestConfig(value="fallback")
        result = reader.read_toml(TestConfig, fallback=fallback)
        assert result == fallback

    os.unlink(f.name)


def test_read_toml_valid() -> None:
    with NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write('value = "test"')
        f.flush()

        reader = ConfigReader(f.name)
        fallback = TestConfig(value="fallback")
        result = reader.read_toml(TestConfig, fallback=fallback)
        assert result == TestConfig(value="test")

    os.unlink(f.name)
