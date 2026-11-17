# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
import difflib
import json
import shlex
import types
from typing import Annotated, Any, Union, get_args, get_origin

import click
import msgspec
from click.core import ParameterSource

from marimo._cli import cli_validators as validators
from marimo._cli.config.utils import _format_type
from marimo._config.config import PartialMarimoConfig
from marimo._config.config_schema import MarimoConfig
from marimo._config.manager import (
    CLIConfigReader,
    MarimoConfigManager,
    get_default_config_manager,
)
from marimo._config.schema_utils import config_cli_flags, config_leaf_types
from marimo._utils.url import is_url


def _variants(annotation: Any) -> tuple[Any, ...]:
    if get_origin(annotation) is Annotated:
        return _variants(get_args(annotation)[0])
    if get_origin(annotation) in (Union, types.UnionType):
        return tuple(
            variant
            for arg in get_args(annotation)
            for variant in _variants(arg)
        )
    return (annotation,)


def _parse_value(raw: str, annotation: Any) -> Any:
    variants = _variants(annotation)
    if raw == "null" and type(None) in variants:
        return None
    try:
        return msgspec.convert(raw, type=annotation, strict=False)
    except msgspec.ValidationError:
        pass
    if collection := next(
        (variant for variant in variants if get_origin(variant) is list),
        None,
    ):
        item_type = get_args(collection)[0]
        try:
            value = json.loads(raw)
        except ValueError:
            pass
        else:
            if isinstance(value, list) or (
                isinstance(item_type, type)
                and issubclass(item_type, msgspec.Struct)
            ):
                return value
        return [_parse_value(item, item_type) for item in shlex.split(raw)]
    # Validate structured values through MarimoConfig, which also normalizes MCP tags.
    return json.loads(raw)


def _set_value(
    config: PartialMarimoConfig, path: tuple[str, ...], value: Any
) -> None:
    current = config
    for component in path[:-1]:
        current = current.setdefault(component, {})
    current[path[-1]] = value


def parse_config_overrides(
    ctx: click.Context, param: click.Parameter, values: tuple[str, ...]
) -> PartialMarimoConfig:
    del ctx
    leaves = config_leaf_types(MarimoConfig)
    overrides: PartialMarimoConfig = {}
    for assignment in values:
        key, separator, raw = assignment.partition("=")
        if not separator:
            raise click.BadParameter(
                "Expected category.name=value, for example display.theme=dark.",
                param=param,
            )
        path = tuple(key.split("."))
        if path not in leaves:
            matches = difflib.get_close_matches(
                key, [".".join(path) for path in leaves], n=1
            )
            suggestion = f" Did you mean {matches[0]!r}?" if matches else ""
            raise click.BadParameter(
                f"Unknown configuration field {key!r}.{suggestion} "
                "Run `marimo config describe` for available fields.",
                param=param,
            )
        try:
            value = _parse_value(raw, leaves[path])
            partial: PartialMarimoConfig = {}
            _set_value(partial, path, value)
            MarimoConfig.from_dict(partial)
        except (ValueError, TypeError):
            # Values may contain credentials, including inside collections.
            raise click.BadParameter(
                f"Invalid value for {key!r}. Expected {_format_type(leaves[path])}. "
                "Run `marimo config describe` "
                "for accepted types and values.",
                param=param,
            ) from None
        _set_value(overrides, path, value)
    return overrides


config_override_option = click.option(
    "--config",
    "config_overrides",
    multiple=True,
    metavar="CATEGORY.NAME=VALUE",
    callback=parse_config_overrides,
    help="Override a configuration field for this invocation. Can be repeated.",
)


def resolve_cli_config(
    *,
    current_path: str | None,
    overrides: PartialMarimoConfig,
) -> MarimoConfigManager:
    ctx = click.get_current_context()
    overrides = copy.deepcopy(overrides)
    for path, names in config_cli_flags(MarimoConfig).items():
        spellings = set(names)
        for param in ctx.command.params:
            if (
                isinstance(param, click.Option)
                and spellings.intersection(param.opts + param.secondary_opts)
                and param.name is not None
                and ctx.get_parameter_source(param.name)
                == ParameterSource.COMMANDLINE
            ):
                value = ctx.params[param.name]
                if param.multiple and isinstance(value, tuple):
                    value = list(value)
                _set_value(overrides, path, value)
    manager = get_default_config_manager(
        current_path=None
        if current_path and is_url(current_path)
        else current_path
    ).with_partial(CLIConfigReader(overrides))
    server = manager.get_config(hide_secrets=False).server
    validators.base_url(None, None, server.base_url)
    return manager
