# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
from typing import (
    TYPE_CHECKING,
    Any,
)

import msgspec
import pytest
from msgspec import UNSET

from marimo._config import config_schema
from marimo._config.config import (
    DEFAULT_CONFIG,
    merge_config,
    merge_default_config,
    parse_config,
)
from marimo._config.config_schema import MarimoConfig
from marimo._config.manager import UserConfigStore
from marimo._config.schema_utils import (
    Config,
    default_if_unset,
)

if TYPE_CHECKING:
    from pathlib import Path

SCHEMA_CLASSES = [
    cls
    for cls in vars(config_schema).values()
    if isinstance(cls, type)
    and issubclass(cls, Config)
    and cls.__module__ == config_schema.__name__
]


def test_schema_defaults_preserve_dictionary_api() -> None:
    defaults = MarimoConfig(
        runtime=config_schema.RuntimeConfig(
            output_max_bytes=DEFAULT_CONFIG.runtime.output_max_bytes,
            std_stream_max_bytes=DEFAULT_CONFIG.runtime.std_stream_max_bytes,
        ),
        package_management=config_schema.PackageManagementConfig(
            manager=DEFAULT_CONFIG.package_management.manager
        ),
    )
    assert defaults == DEFAULT_CONFIG
    resolved = merge_default_config({"display": {"theme": "dark"}})
    assert isinstance(resolved, MarimoConfig)
    assert resolved.display.to_dict() == {
        **DEFAULT_CONFIG.display.to_dict(),
        "theme": "dark",
    }


def test_runtime_defaults_ignore_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MARIMO_RUNTIME_OUTPUT_MAX_BYTES", "1234")
    monkeypatch.setenv("MARIMO_RUNTIME_STD_STREAM_MAX_BYTES", "5678")
    assert config_schema.RuntimeConfig().to_dict() == {
        **DEFAULT_CONFIG.runtime.to_dict(),
        "output_max_bytes": 8_000_000,
        "std_stream_max_bytes": 1_000_000,
    }


@pytest.mark.parametrize("cls", SCHEMA_CLASSES, ids=lambda cls: cls.__name__)
def test_schema_fields_have_descriptions(cls: type[Config]) -> None:
    assert issubclass(cls, msgspec.Struct)
    properties = msgspec.json.schema(cls)["$defs"][cls.__name__]["properties"]
    assert all(
        properties[name].get("description") for name in cls.__struct_fields__
    )


def test_defaults_are_independent() -> None:
    first = MarimoConfig()
    second = MarimoConfig()
    before = second.to_dict()
    first.ai.models.displayed_models.append("custom-model")
    first.keymap.overrides["run"] = "Ctrl-Enter"
    first.mcp.presets.append("marimo")
    first.runtime.pythonpath.append("/custom")
    first.runtime.default_auto_download.append("html")
    first.experimental.debugger = True
    first.cache.loader = "json"
    first.venv.writable = True
    first.signing.trusted_signers["fingerprint"] = "label"
    first.lint.ignore.append("MF001")
    first.datasources.auto_discover_tables = False

    assert second.to_dict() == before


def test_optional_sections_default_to_none() -> None:
    config = MarimoConfig()
    assert {
        "sharing": config.sharing,
        "file_browser": config.file_browser,
    } == {
        "sharing": None,
        "file_browser": None,
    }
    assert (
        MarimoConfig.from_dict(config.to_dict()).to_dict() == config.to_dict()
    )


@pytest.mark.parametrize("field", ["dotenv", "sql_default_limit"])
def test_contextual_defaults_keep_omission_distinct(field: str) -> None:
    assert field not in MarimoConfig().runtime.to_dict()
    value = [] if field == "dotenv" else None
    config = MarimoConfig.from_dict({"runtime": {field: value}})
    assert config.runtime.to_dict()[field] == value


@pytest.mark.parametrize(
    ("value", "expected"),
    [(UNSET, "fallback"), (None, None), (False, False), (0, 0), ("", "")],
)
def test_default_if_unset_preserves_explicit_values(
    value: Any, expected: Any
) -> None:
    assert default_if_unset(value, "fallback") == expected


def test_nested_conversion_preserves_presence() -> None:
    config = config_schema.AiConfig.from_dict(
        {
            "max_tokens": None,
            "open_ai": {"api_key": "secret"},
            "custom_providers": {
                "gateway": {"base_url": "https://example.com"}
            },
        }
    )
    assert isinstance(config.open_ai, config_schema.OpenAiConfig)
    assert isinstance(
        config.custom_providers["gateway"], config_schema.OpenAiConfig
    )
    assert config.to_dict() == {
        "enabled": True,
        "rules": "",
        "mode": "ask",
        "allow_provider_config": True,
        "models": {
            "chat_model": None,
            "edit_model": None,
            "autocomplete_model": None,
            "displayed_models": [],
            "custom_models": [],
        },
        "max_tokens": None,
        "open_ai": {"api_key": "secret"},
        "custom_providers": {"gateway": {"base_url": "https://example.com"}},
    }
    assert "secret" not in repr(config)


def test_list_and_union_conversion() -> None:
    folders = config_schema.FileBrowserConfig.from_dict(
        {"folders": [{"path": "/data"}]}
    )
    assert folders.folders == [config_schema.FolderConfig(path="/data")]
    assert folders.to_dict() == {"folders": [{"path": "/data", "name": None}]}

    mcp = config_schema.MCPConfig.from_dict(
        {
            "mcpServers": {
                "stdio": {"command": "python"},
                "http": {"url": "https://example.com"},
            }
        }
    )
    assert mcp.mcpServers == {
        "stdio": config_schema.MCPServerStdioConfig(command="python"),
        "http": config_schema.MCPServerStreamableHttpConfig(
            url="https://example.com"
        ),
    }


def test_unknown_fields_survive_resolution_and_merging() -> None:
    config = MarimoConfig.from_dict(
        {
            "future_section": {"value": [1, 2]},
            "runtime": {"future_setting": None},
            "experimental": {"multi_column": True},
            "ai": {
                "custom_providers": {"gateway": {"future_option": "value"}}
            },
        }
    )
    merged = merge_config(
        config.to_dict(), {"experimental": {"debugger": False}}
    )
    serialized = merged.to_dict()

    assert serialized["future_section"] == {"value": [1, 2]}
    assert serialized["runtime"]["future_setting"] is None
    assert serialized["experimental"] == {
        "isolate_apps": False,
        "line_timing": False,
        "execution_type": "relaxed",
        "multi_column": True,
        "debugger": False,
    }
    assert serialized["ai"]["custom_providers"] == {
        "gateway": {"future_option": "value"}
    }
    assert MarimoConfig.from_dict(serialized).to_dict() == serialized
    assert config.to_dict()["experimental"] == {
        "isolate_apps": False,
        "debugger": False,
        "line_timing": False,
        "execution_type": "relaxed",
        "multi_column": True,
    }


def test_unknown_fields_are_copied() -> None:
    source = {"future_section": {"values": [1]}}
    config = MarimoConfig.from_dict(source)
    source["future_section"]["values"].append(2)
    serialized = config.to_dict()
    serialized["future_section"]["values"].append(3)

    assert config.to_dict()["future_section"] == {"values": [1]}


def test_saving_config_preserves_unknown_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "marimo.toml"
    path.write_text(
        '[experimental]\nmulti_column = true\n\n[future_section]\nvalue = "kept"\n'
    )
    store = UserConfigStore()
    monkeypatch.setattr(store, "get_config_path", lambda: str(path))

    saved = store.save_config({"experimental": {"debugger": False}})

    assert saved.to_dict()["experimental"] == {
        "isolate_apps": False,
        "line_timing": False,
        "execution_type": "relaxed",
        "multi_column": True,
        "debugger": False,
    }
    assert store.read()["experimental"] == {
        "isolate_apps": False,
        "line_timing": False,
        "execution_type": "relaxed",
        "multi_column": True,
        "debugger": False,
    }
    assert store.read()["future_section"] == {"value": "kept"}  # type: ignore[typeddict-item]


@pytest.mark.parametrize(
    ("values", "path"),
    [
        ({"save": {"autosave_delay": "fast"}}, "$.save.autosave_delay"),
        ({"display": {"theme": "invalid"}}, "$.display.theme"),
        (
            {"ai": {"models": {"displayed_models": [42]}}},
            "$.ai.models.displayed_models[0]",
        ),
    ],
)
def test_conversion_validates_known_fields(
    values: dict[str, Any], path: str
) -> None:
    with pytest.raises(msgspec.ValidationError) as error:
        MarimoConfig.from_dict(values)
    assert path in str(error.value)


def test_mcp_round_trip_preserves_legacy_input_and_unknown_fields() -> None:
    servers = {
        "stdio": {"command": "python", "args": None, "future": {"value": 1}},
        "http": {"url": "https://example.com", "timeout": 2.5},
        "both": {"command": "python", "url": "https://example.com"},
    }
    config = MarimoConfig.from_dict({"mcp": {"mcpServers": servers}})
    assert config.mcp.to_dict() == {"mcpServers": servers, "presets": []}
    assert isinstance(
        config.mcp.mcpServers["both"], config_schema.MCPServerStdioConfig
    )
    assert (
        config_schema.MCPConfig.from_dict({"mcpServers": servers})
        == config.mcp
    )
    assert servers["stdio"] == {
        "command": "python",
        "args": None,
        "future": {"value": 1},
    }


def test_mcp_missing_transport_fields_is_rejected() -> None:
    with pytest.raises(msgspec.ValidationError, match="__marimo_transport__"):
        config_schema.MCPConfig.from_dict(
            {"mcpServers": {"broken": {"args": []}}}
        )


def test_unknown_fields_in_lists_follow_their_objects() -> None:
    config = config_schema.FileBrowserConfig.from_dict(
        {
            "folders": [
                {"path": "/first", "future": {"value": [1]}},
                {"path": "/second", "label": "retained"},
            ]
        }
    )
    assert isinstance(config.folders, list)
    config.folders.reverse()
    assert config.to_dict() == {
        "folders": [
            {"path": "/second", "name": None, "label": "retained"},
            {"path": "/first", "name": None, "future": {"value": [1]}},
        ]
    }
    serialized = config.to_dict()
    serialized["folders"][1]["future"]["value"].append(2)
    assert config.to_dict()["folders"][1]["future"] == {"value": [1]}


def test_metadata_describes_and_hides_secrets() -> None:
    config = config_schema.OpenAiConfig(
        api_key="secret", base_url="https://example.com"
    )
    assert "secret" not in repr(config)
    assert dict(config.__rich_repr__()) == {
        name: getattr(config, name)
        for name in config.__struct_fields__
        if name not in {"api_key", "extra_headers"}
    }
    schema = msgspec.json.schema(config_schema.OpenAiConfig)["$defs"][
        "OpenAiConfig"
    ]
    assert schema["properties"]["model"]["deprecated"] is True
    assert (
        schema["properties"]["api_key"]["description"]
        == "the OpenAI API key or an `env:` reference"
    )


@pytest.mark.parametrize("loader", ["pickle", "json", "lazy", "custom"])
def test_cache_loader_accepts_builtin_and_custom_names(loader: str) -> None:
    config = config_schema.CacheConfig.from_dict({"loader": loader})
    assert config.loader == loader
    assert config.to_dict() == {
        "verification": "off",
        "store": None,
        "loader": loader,
    }


def test_cache_store_union_uses_struct_conversion() -> None:
    for store in (
        {"type": "file", "args": {"path": "/cache"}},
        [{"type": "file", "args": {}}, {"type": "redis", "args": {}}],
    ):
        config = config_schema.CacheConfig.from_dict({"store": store})
        assert config.to_dict() == {
            "verification": "off",
            "store": store,
            "loader": "lazy",
        }
        if isinstance(config.store, list):
            assert all(
                isinstance(item, config_schema.StoreConfig)
                for item in config.store
            )
        else:
            assert isinstance(config.store, config_schema.StoreConfig)


@pytest.mark.parametrize(
    ("cls", "field_name", "settings"),
    [
        (config_schema.OpenAiConfig, "extra_headers", {}),
        (config_schema.MCPServerStdioConfig, "env", {"command": "python"}),
        (
            config_schema.MCPServerStreamableHttpConfig,
            "env",
            {"url": "https://example.com"},
        ),
        (
            config_schema.MCPServerStreamableHttpConfig,
            "headers",
            {"url": "https://example.com"},
        ),
    ],
)
def test_credential_mappings_are_hidden_from_representations(
    cls: type[Config], field_name: str, settings: dict[str, Any]
) -> None:
    credentials = {"AUTHORIZATION": "credential-mapping-secret"}
    config = cls.from_dict({**settings, field_name: credentials})

    assert "credential-mapping-secret" not in repr(config)
    assert "credential-mapping-secret" not in repr(config.__rich_repr__())
    assert field_name not in dict(config.__rich_repr__())
    assert config.to_dict()[field_name] == credentials


def test_deepcopy_isolates_schema_settings() -> None:
    original = MarimoConfig.from_dict(
        {
            "runtime": {"pythonpath": ["/original"]},
            "future": {"values": [1]},
        }
    )
    before = original.to_dict()
    copied = copy.deepcopy(original)
    copied.keymap.overrides["run"] = "Ctrl-Enter"
    paths = copied.runtime.pythonpath
    assert paths is not UNSET
    paths.append("/copy")
    extra = copied._extra_fields["future"]
    assert isinstance(extra, dict)
    extra["values"].append(2)

    assert original.to_dict() == before


def test_manager_defaults_invalid_fields_without_losing_valid_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from marimo._config.manager import MarimoConfigManager

    path = tmp_path / "marimo.toml"
    path.write_text(
        '[display]\ntheme = "invalid"\ncode_editor_font_size = 16\n'
        '[runtime]\noutput_max_bytes = "invalid"\n'
        '[future]\nvalue = "preserved"\n'
    )
    store = UserConfigStore()
    monkeypatch.setattr(store, "get_config_path", lambda: str(path))
    resolved = MarimoConfigManager(store).get_config()

    expected = DEFAULT_CONFIG.to_dict()
    expected["display"]["code_editor_font_size"] = 16
    expected["future"] = {"value": "preserved"}
    assert isinstance(resolved, MarimoConfig)
    assert resolved.to_dict() == expected
    assert str(path) in caplog.text


def test_configuration_wire_round_trip_preserves_external_format() -> None:
    from marimo._ast.app_config import _AppConfig
    from marimo._ipc.types import ConnectionInfo, KernelArgs
    from marimo._messaging.msgspec_encoder import encode_json_bytes
    from marimo._runtime.commands import AppMetadata, UpdateUserConfigCommand

    config = MarimoConfig.from_dict(
        {
            "mcp": {
                "mcpServers": {"local": {"command": "python", "future": 1}}
            },
            "runtime": {"future": True},
        }
    )
    payload = config.to_dict()
    command = UpdateUserConfigCommand(config=payload)
    decoded_command = msgspec.json.decode(
        encode_json_bytes(command), type=UpdateUserConfigCommand
    )
    args = KernelArgs(
        configs={},
        app_metadata=AppMetadata(
            query_params={}, cli_args={}, app_config=_AppConfig()
        ),
        user_config=payload,
        log_level=0,
        profile_path=None,
        connection_info=ConnectionInfo(
            control=1,
            ui_element=2,
            completion=3,
            win32_interrupt=None,
            input=4,
            stream=5,
        ),
    )
    decoded_args = KernelArgs.decode_json(args.encode_json())

    assert decoded_command.config == payload
    assert decoded_args.user_config == payload
    assert (
        MarimoConfig.from_dict(decoded_args.user_config).to_dict() == payload
    )
    assert "__marimo_transport__" not in payload["mcp"]["mcpServers"]["local"]


@pytest.mark.parametrize(
    "store", ["file", "redis", "rest", "tiered", "custom"]
)
def test_cache_store_accepts_builtin_and_custom_names(store: str) -> None:
    config = config_schema.StoreConfig.from_dict({"type": store})
    assert config.to_dict() == {"type": store, "args": {}}


def test_removed_codeium_provider_preserves_other_settings() -> None:
    config = parse_config(
        {
            "completion": {
                "copilot": "codeium",
                "codeium_api_key": "legacy-secret",
                "auto_close_pairs": False,
            },
            "display": {"theme": "dark"},
        }
    )
    assert config == MarimoConfig(
        completion=config_schema.CompletionConfig(auto_close_pairs=False),
        display=config_schema.DisplayConfig(theme="dark"),
    )
