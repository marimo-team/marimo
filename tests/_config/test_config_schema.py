# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import types
from typing import (
    TYPE_CHECKING,
    Any,
    NotRequired,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

import msgspec
import pytest
from msgspec import UNSET, UnsetType

from marimo._config import config as legacy_config, config_schema
from marimo._config.config import (
    DEFAULT_CONFIG,
    merge_config,
    merge_default_config,
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
            output_max_bytes=DEFAULT_CONFIG["runtime"]["output_max_bytes"],
            std_stream_max_bytes=DEFAULT_CONFIG["runtime"][
                "std_stream_max_bytes"
            ],
        ),
        package_management=config_schema.PackageManagementConfig(
            manager=DEFAULT_CONFIG["package_management"]["manager"]
        ),
    )
    assert defaults.to_dict() == DEFAULT_CONFIG
    resolved = merge_default_config({"display": {"theme": "dark"}})
    assert isinstance(resolved, dict)
    assert resolved["display"] == {
        **DEFAULT_CONFIG["display"],
        "theme": "dark",
    }


def test_runtime_defaults_ignore_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MARIMO_OUTPUT_MAX_BYTES", "1234")
    monkeypatch.setenv("MARIMO_STD_STREAM_MAX_BYTES", "5678")
    assert config_schema.RuntimeConfig().to_dict() == {
        **DEFAULT_CONFIG["runtime"],
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


def _normalize_type(annotation: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is NotRequired:
        return _normalize_type(args[0])
    if origin in (Union, types.UnionType):
        present = [
            _normalize_type(arg) for arg in args if arg is not UnsetType
        ]
        return present[0] if len(present) == 1 else frozenset(present)
    if origin is not None:
        return (origin, tuple(_normalize_type(arg) for arg in args))
    if isinstance(annotation, type) and (
        issubclass(annotation, Config)
        or hasattr(annotation, "__required_keys__")
    ):
        return annotation.__name__
    return annotation


@pytest.mark.parametrize("cls", SCHEMA_CLASSES, ids=lambda cls: cls.__name__)
def test_schema_preserves_existing_field_types(cls: type[Config]) -> None:
    legacy_cls = getattr(legacy_config, cls.__name__)
    legacy_hints = get_type_hints(
        legacy_cls,
        localns={
            "MCPServerConfig": legacy_config.MCPServerStdioConfig
            | legacy_config.MCPServerStreamableHttpConfig
        },
        include_extras=True,
    )
    schema_hints = get_type_hints(cls)
    for name, annotation in legacy_hints.items():
        if cls is MarimoConfig and name == "experimental":
            continue
        # These scalars can be cleared with null by the settings UI.
        if (cls is config_schema.AiConfig and name == "max_tokens") or (
            cls is config_schema.AiModelConfig
            and name in {"chat_model", "edit_model", "autocomplete_model"}
        ):
            annotation = Union[annotation, None]
        assert _normalize_type(schema_hints[name]) == _normalize_type(
            annotation
        )


def test_defaults_are_independent() -> None:
    first = MarimoConfig()
    second = MarimoConfig()
    before = second.to_dict()
    first.ai.models.displayed_models.append("custom-model")
    first.keymap.overrides["run"] = "Ctrl-Enter"
    first.mcp.presets.append("marimo")

    assert second.to_dict() == before


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
        "allow_provider_config": True,
        "models": {"displayed_models": [], "custom_models": []},
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
    assert folders.to_dict() == {"folders": [{"path": "/data"}]}

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
    serialized = merged

    assert serialized["future_section"] == {"value": [1, 2]}
    assert serialized["runtime"]["future_setting"] is None
    assert serialized["experimental"] == {
        "multi_column": True,
        "debugger": False,
    }
    assert serialized["ai"]["custom_providers"] == {
        "gateway": {"future_option": "value"}
    }
    assert MarimoConfig.from_dict(serialized).to_dict() == serialized
    assert config.to_dict()["experimental"] == {"multi_column": True}


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

    assert saved["experimental"] == {
        "multi_column": True,
        "debugger": False,
    }
    assert store.read()["experimental"] == {
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
            {"path": "/second", "label": "retained"},
            {"path": "/first", "future": {"value": [1]}},
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
    assert config.to_dict() == {"loader": loader}


def test_cache_store_union_uses_struct_conversion() -> None:
    for store in (
        {"type": "file", "args": {"path": "/cache"}},
        [{"type": "file"}, {"type": "redis"}],
    ):
        config = config_schema.CacheConfig.from_dict({"store": store})
        assert config.to_dict() == {"store": store}
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
