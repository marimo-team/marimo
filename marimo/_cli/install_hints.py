# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from marimo._config.packages import PackageManagerKind, infer_package_manager
from marimo._utils.platform import is_windows


@dataclass(frozen=True)
class CommandRule:
    manager: PackageManagerKind
    context: str
    template: str


_INSTALL_COMMAND_RULES: Final[tuple[CommandRule, ...]] = (
    CommandRule("uv", "project", "uv add {packages}"),
    CommandRule("uv", "any", "uv pip install {packages}"),
    CommandRule("pixi", "any", "pixi add {packages}"),
    CommandRule("poetry", "any", "poetry add {packages}"),
    CommandRule("rye", "any", "rye add {packages}"),
    CommandRule("pip", "any", "python -m pip install {packages}"),
)

_POST_INSTALL_COMMAND_RULES: Final[tuple[CommandRule, ...]] = (
    CommandRule("uv", "project", "uv run {command}"),
    CommandRule("pixi", "any", "pixi run {command}"),
    CommandRule("poetry", "any", "poetry run {command}"),
    CommandRule("rye", "any", "rye run {command}"),
    CommandRule("pip", "any", "{module_fallback}"),
)

_UPGRADE_COMMAND_RULES: Final[tuple[CommandRule, ...]] = (
    CommandRule("uv", "project", "uv add --upgrade {packages}"),
    CommandRule("uv", "any", "uv pip install --upgrade {packages}"),
    CommandRule("pixi", "any", "pixi upgrade {packages}"),
    CommandRule("poetry", "any", "poetry update --no-interaction {packages}"),
    CommandRule("rye", "any", "rye sync --update {packages}"),
    CommandRule("pip", "any", "python -m pip install --upgrade {packages}"),
)


def _is_uv_project_context() -> bool:
    """Return whether the current environment matches a uv project venv."""
    uv_project_environment = os.environ.get("UV_PROJECT_ENVIRONMENT")
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if uv_project_environment and uv_project_environment == virtual_env:
        return True

    cwd = Path.cwd()
    for path in (cwd, *cwd.parents):
        if (path / "pyproject.toml").exists() and (path / "uv.lock").exists():
            return True
    return False


def _normalize_packages(packages: str | list[str] | tuple[str, ...]) -> str:
    if isinstance(packages, str):
        package_tokens = packages.split()
    else:
        package_tokens = [
            package.strip() for package in packages if package.strip()
        ]
    return " ".join(
        _quote_package_token(package) for package in package_tokens
    )


def _quote_package_token(package: str) -> str:
    if "[" not in package and "]" not in package:
        return package
    if is_windows():
        return package
    escaped = package.replace("'", "'\"'\"'")
    return f"'{escaped}'"


def _normalize_command(command: str) -> str:
    return command.strip()


def _resolve_manager_context() -> tuple[PackageManagerKind, str]:
    """Infer package manager and whether uv should use project-local commands."""
    manager = infer_package_manager()
    context = (
        "project" if manager == "uv" and _is_uv_project_context() else "any"
    )
    return manager, context


def _resolve_template(
    rules: tuple[CommandRule, ...],
    manager: PackageManagerKind,
    *,
    context: str,
) -> str | None:
    """Select the first command template matching manager and context."""
    for rule in rules:
        if rule.manager != manager:
            continue
        if rule.context not in ("any", context):
            continue
        return rule.template
    return None


def _build_primary_and_fallback(
    *,
    rules: tuple[CommandRule, ...],
    format_args: dict[str, str],
) -> list[str]:
    """Build primary and pip-fallback commands from declarative templates."""
    manager, context = _resolve_manager_context()
    template = _resolve_template(rules, manager, context=context)
    fallback_template = _resolve_template(rules, "pip", context="any")
    assert fallback_template is not None

    primary_command = (
        template.format(**format_args)
        if template is not None
        else fallback_template.format(**format_args)
    )
    pip_fallback_command = fallback_template.format(**format_args)

    if primary_command == pip_fallback_command:
        return [primary_command]
    return [primary_command, pip_fallback_command]


def get_install_commands(
    packages: str | list[str] | tuple[str, ...],
) -> list[str]:
    package_text = _normalize_packages(packages)
    if not package_text:
        return []
    return _build_primary_and_fallback(
        rules=_INSTALL_COMMAND_RULES,
        format_args={"packages": package_text},
    )


def get_post_install_commands(
    command: str, *, module_fallback: str | None = None
) -> list[str]:
    command_text = _normalize_command(command)
    if not command_text:
        return []

    fallback = _normalize_command(module_fallback or command_text)
    if not fallback:
        return []

    return _build_primary_and_fallback(
        rules=_POST_INSTALL_COMMAND_RULES,
        format_args={
            "command": command_text,
            "module_fallback": fallback,
        },
    )


def get_upgrade_commands(
    packages: str | list[str] | tuple[str, ...],
) -> list[str]:
    package_text = _normalize_packages(packages)
    if not package_text:
        return []
    return _build_primary_and_fallback(
        rules=_UPGRADE_COMMAND_RULES,
        format_args={"packages": package_text},
    )


def get_playwright_chromium_setup_commands() -> list[str]:
    return get_post_install_commands(
        "playwright install chromium",
        module_fallback="python -m playwright install chromium",
    )
