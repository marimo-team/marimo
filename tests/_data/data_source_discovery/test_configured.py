# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.data_source_discovery.configured import (
    DiscoveryNamespaceContext,
    is_data_source_already_configured,
)
from marimo._data.data_source_discovery.helpers import ENVIRONMENT_ORIGIN
from marimo._data.data_source_discovery.models import (
    DataSourceCategory,
    DetectedDataSource,
)
from marimo._data.data_source_discovery.plugins import (
    DEFAULT_DISCOVERY_PLUGINS,
)
from marimo._data.data_source_discovery.types import (
    DialectMatch,
    DiscoveryContext,
    DiscoveryPlugin,
)


def detected_source(
    *,
    integration: str,
    category: DataSourceCategory,
) -> DetectedDataSource:
    return DetectedDataSource(
        id=integration,
        integration=integration,
        category=category,
        display_name=integration,
        confidence="high",
        origins=(ENVIRONMENT_ORIGIN,),
        configuration=(),
        code="",
    )


def test_database_source_unconfigured_without_matching_connection() -> None:
    source = detected_source(integration="postgres", category="database")
    namespace = DiscoveryNamespaceContext((), (), ())

    assert not is_data_source_already_configured(source, namespace)


def test_database_source_matches_by_sql_dialect_substring() -> None:
    source = detected_source(integration="postgres", category="database")
    namespace = DiscoveryNamespaceContext(("postgresql",), (), ())

    assert is_data_source_already_configured(source, namespace)


def test_pyiceberg_matches_iceberg_dialect() -> None:
    source = detected_source(integration="pyiceberg", category="catalog")
    namespace = DiscoveryNamespaceContext(("iceberg",), (), ())

    assert is_data_source_already_configured(source, namespace)


def test_unrelated_dialect_does_not_match() -> None:
    source = detected_source(integration="mysql", category="database")
    namespace = DiscoveryNamespaceContext(("postgresql",), (), ())

    assert not is_data_source_already_configured(source, namespace)


def test_aws_matches_s3_compatible_storage_protocols() -> None:
    source = detected_source(integration="aws", category="object-storage")

    for protocol in ("s3", "cloudflare", "coreweave"):
        namespace = DiscoveryNamespaceContext((), (protocol,), ())
        assert is_data_source_already_configured(source, namespace)


def test_huggingface_matches_huggingface_backend() -> None:
    source = detected_source(
        integration="huggingface", category="object-storage"
    )
    namespace = DiscoveryNamespaceContext((), ("hf",), ("huggingface",))

    assert is_data_source_already_configured(source, namespace)


def test_object_storage_does_not_match_unrelated_namespace() -> None:
    source = detected_source(integration="aws", category="object-storage")
    namespace = DiscoveryNamespaceContext((), ("gcs",), ("obstore",))

    assert not is_data_source_already_configured(source, namespace)


def test_unknown_integration_is_not_configured() -> None:
    source = detected_source(integration="unknown", category="database")
    namespace = DiscoveryNamespaceContext(("postgresql",), ("s3",), ())

    assert not is_data_source_already_configured(source, namespace)


def test_custom_plugin_configured_when_is_used() -> None:
    source = detected_source(integration="custom", category="database")
    plugin = DiscoveryPlugin(
        id="custom",
        discover=lambda _context: [source],
        configured_when=DialectMatch(substrings=("custom-dialect",)),
    )
    namespace = DiscoveryNamespaceContext(("custom-dialect",), (), ())

    assert is_data_source_already_configured(
        source, namespace, plugins=(plugin,)
    )
    assert not is_data_source_already_configured(source, namespace)


def test_default_plugins_cannot_omit_a_configured_when_rule() -> None:
    ids = [plugin.id for plugin in DEFAULT_DISCOVERY_PLUGINS]
    assert len(ids) == len(set(ids))

    for plugin in DEFAULT_DISCOVERY_PLUGINS:
        rule = plugin.configured_when
        if isinstance(rule, DialectMatch):
            namespace = DiscoveryNamespaceContext(rule.substrings, (), ())
        else:
            namespace = DiscoveryNamespaceContext(
                (), rule.protocols, rule.backend_types
            )
        assert rule.matches(namespace), plugin.id


def test_default_plugins_emit_their_own_integration() -> None:
    context = DiscoveryContext(
        environment={
            "PGHOST": "host",
            "PGUSER": "user",
            "PGDATABASE": "database",
            "MYSQL_HOST": "host",
            "MYSQL_USER": "user",
            "MYSQL_DATABASE": "database",
            "MYSQL_PASSWORD": "password",
            "AWS_PROFILE": "default",
            "TRINO_HOST": "host",
            "TRINO_USER": "user",
            "TRINO_CATALOG": "catalog",
            "SPARK_REMOTE": "sc://host:1",
            "PYICEBERG_CATALOG__PROD__URI": "https://example.invalid",
            "HF_TOKEN": "token",
        }
    )
    for plugin in DEFAULT_DISCOVERY_PLUGINS:
        for source in plugin.discover(context):
            assert source.integration == plugin.id
