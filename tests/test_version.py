# Copyright 2026 Marimo. All rights reserved.

from importlib.metadata import PackageNotFoundError

import pytest

from marimo import _version


def test_get_version_from_marimo(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_version(distribution: str) -> str:
        assert distribution == "marimo"
        return "1.2.3"

    monkeypatch.setattr(_version, "version", get_version)

    assert _version._get_version() == "1.2.3"


def test_get_version_from_marimo_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def get_version(distribution: str) -> str:
        if distribution == "marimo-base":
            return "1.2.3"
        raise PackageNotFoundError(distribution)

    monkeypatch.setattr(_version, "version", get_version)

    assert _version._get_version() == "1.2.3"


def test_get_version_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def get_version(distribution: str) -> str:
        raise PackageNotFoundError(distribution)

    monkeypatch.setattr(_version, "version", get_version)

    assert _version._get_version() == "unknown"
