# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from marimo import _loggers
from marimo._config.config import DEFAULT_CONFIG
from marimo._config.deprecations import (
    _warn_deprecated_field,
    warn_deprecated_fields,
)
from marimo._config.manager import (
    EnvVarReader,
    MarimoConfigManager,
    PyprojectConfigReader,
    ScriptConfigReader,
    UserConfigStore,
)
from marimo._config.provenance import ConfigLayer


@pytest.fixture(autouse=True)
def clear_warnings() -> None:
    _warn_deprecated_field.cache_clear()


@pytest.mark.parametrize("source", ["user", "pyproject", "script", "env"])
def test_deprecated_field_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    user_path = tmp_path / ".marimo.toml"
    user_path.write_text("")
    store = UserConfigStore(create_if_missing=False)
    readers = []
    if source == "user":
        user_path.write_text('[completion]\napi_key = "secret-api-key"\n')
        field = "completion.api_key"
        guidance = "Use an AI provider configuration instead."
        location = str(user_path)
    elif source == "pyproject":
        project_path = tmp_path / "pyproject.toml"
        project_path.write_text(
            '[tool.marimo.completion]\napi_key = "secret-api-key"\n'
        )
        readers.append(PyprojectConfigReader(str(tmp_path)))
        field = "completion.api_key"
        guidance = "Use an AI provider configuration instead."
        location = str(project_path)
    elif source == "script":
        script_path = tmp_path / "notebook.py"
        script_path.write_text(
            "# /// script\n# [tool.marimo.experimental]\n"
            "# external_agents = false\n# ///\n"
        )
        readers.append(ScriptConfigReader(str(script_path)))
        field = "experimental.external_agents"
        guidance = "prefer marimo pair"
        location = str(script_path)
    else:
        monkeypatch.setenv("MARIMO_COMPLETION_API_KEY", "secret-api-key")
        readers.append(EnvVarReader())
        field = "completion.api_key"
        guidance = "Use an AI provider configuration instead."
        location = "env var: MARIMO_COMPLETION_API_KEY"

    with (
        patch.object(store, "get_config_path", return_value=str(user_path)),
        _loggers.capture_output(log_level=logging.WARNING) as (_, _, records),
    ):
        manager = MarimoConfigManager(store, *readers)
        manager.get_config()
        manager.get_config(hide_secrets=False)
        manager.get_user_config()
        manager.get_config_overrides()
        # New managers reading the same source should remain quiet, too.
        MarimoConfigManager(store, *readers).get_config()

    messages = [record.getMessage() for record in records]
    assert len(messages) == 1
    assert field in messages[0]
    assert location in messages[0]
    assert guidance in messages[0]
    assert "secret-api-key" not in messages[0]


def test_deprecated_sections_and_record_fields() -> None:
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        warn_deprecated_fields(
            ConfigLayer(
                {
                    "ai": {
                        "open_ai_compatible": {},
                        "custom_providers": {
                            "private-provider": {"model": "private-model"}
                        },
                    }
                },
                Path("marimo.toml"),
            )
        )
    assert [record.getMessage() for record in records] == [
        (
            "Configuration field ai.custom_providers.*.model from marimo.toml "
            "is deprecated. Deprecated chat model. Use ai.models.chat_model instead."
        ),
        (
            "Configuration field ai.open_ai_compatible from marimo.toml "
            "is deprecated. the OpenAI-compatible config (deprecated, use custom_providers)"
        ),
    ]


def test_environment_deprecated_section_reports_supplied_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MARIMO_AI_OPEN_AI_COMPATIBLE_API_KEY", "private-key")
    monkeypatch.setenv("MARIMO_AI_OPEN_AI_COMPATIBLE_BASE_URL", "private-url")
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        EnvVarReader().read_layer()
        EnvVarReader().read_layer()
    messages = [record.getMessage() for record in records]
    assert len(messages) == 2
    assert all("ai.open_ai_compatible" in message for message in messages)
    assert "MARIMO_AI_OPEN_AI_COMPATIBLE_API_KEY" in messages[0]
    assert "MARIMO_AI_OPEN_AI_COMPATIBLE_BASE_URL" in messages[1]
    assert all("private-" not in message for message in messages)


def test_only_explicit_deprecated_fields_warn() -> None:
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        warn_deprecated_fields(
            ConfigLayer(DEFAULT_CONFIG.to_dict(), "default")
        )
        warn_deprecated_fields(
            ConfigLayer(
                {"experimental": {"external_agents": False}}, "inferred"
            )
        )
        warn_deprecated_fields(
            ConfigLayer({"display": {"theme": "dark"}}, Path("marimo.toml"))
        )
        warn_deprecated_fields(ConfigLayer({}, Path("marimo.toml")))
    assert records == []


def test_same_field_in_different_sources_warns_separately() -> None:
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        for source in (Path("one.toml"), Path("two.toml"), Path("one.toml")):
            warn_deprecated_fields(
                ConfigLayer({"completion": {"model": None}}, source)
            )
    assert len(records) == 2
    assert "one.toml" in records[0].getMessage()
    assert "two.toml" in records[1].getMessage()
