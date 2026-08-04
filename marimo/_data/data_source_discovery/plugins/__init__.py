# Copyright 2026 Marimo. All rights reserved.
from marimo._data.data_source_discovery.plugins.aws import AWS_PLUGIN
from marimo._data.data_source_discovery.plugins.huggingface import (
    HUGGINGFACE_PLUGIN,
)
from marimo._data.data_source_discovery.plugins.mysql import MYSQL_PLUGIN
from marimo._data.data_source_discovery.plugins.postgres import POSTGRES_PLUGIN
from marimo._data.data_source_discovery.plugins.pyiceberg import (
    PYICEBERG_PLUGIN,
)
from marimo._data.data_source_discovery.plugins.pyspark import PYSPARK_PLUGIN
from marimo._data.data_source_discovery.plugins.trino import TRINO_PLUGIN
from marimo._data.data_source_discovery.types import DiscoveryPlugin

DEFAULT_DISCOVERY_PLUGINS: tuple[DiscoveryPlugin, ...] = (
    POSTGRES_PLUGIN,
    MYSQL_PLUGIN,
    AWS_PLUGIN,
    TRINO_PLUGIN,
    PYSPARK_PLUGIN,
    PYICEBERG_PLUGIN,
    HUGGINGFACE_PLUGIN,
)

__all__ = ["DEFAULT_DISCOVERY_PLUGINS"]
