# Copyright 2026 Marimo. All rights reserved.
"""Test that all POST endpoints have @requires decorator for auth."""

from __future__ import annotations

import ast
from pathlib import Path

# Endpoints that are intentionally exempt from @requires.
# Each entry is (filename, path).
EXEMPT_ENDPOINTS: set[tuple[str, str]] = {
    # Login endpoints must be accessible without authentication
    ("login.py", "/login"),
    # Service worker must load before auth
    ("assets.py", "/public-files-sw.js"),
    # Static frontend assets (JS/CSS) must load before auth
    ("assets.py", "/{path:path}"),
    # `/` does its own scope check so it can emit a relative Location on
    # unauthenticated redirects (see #9249).
    ("assets.py", "/"),
    # Virtual files do their own scope check so the check can be bypassed
    # via `_MARIMO_DISABLE_AUTH_ON_VIRTUAL_FILES` for sandboxed/embedded
    # deployments.
    ("assets.py", "/@file/{filename_and_length:path}"),
}

ENDPOINTS_DIR = Path(__file__).resolve().parents[4] / (
    "marimo/_server/api/endpoints"
)


def _get_endpoints_missing_requires(
    methods: tuple[str, ...] = ("post", "get"),
) -> list[str]:
    """Parse all endpoint files and find routes missing @requires."""
    missing: list[str] = []

    for filepath in sorted(ENDPOINTS_DIR.glob("*.py")):
        filename = filepath.name
        if filename.startswith("_"):
            continue

        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            route_method: str | None = None
            route_path: str | None = None
            has_requires = False

            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func

                # Check for router.<method>(...)
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr in methods
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "router"
                    and decorator.args
                ):
                    route_method = func.attr.upper()
                    route_path = ast.literal_eval(decorator.args[0])

                # Check for requires(...)
                if isinstance(func, ast.Name) and func.id == "requires":
                    has_requires = True

            if route_method and not has_requires:
                if (filename, route_path) not in EXEMPT_ENDPOINTS:
                    missing.append(
                        f"{filename}: {route_method} {route_path} "
                        f"(function: {node.name}, line: {node.lineno})"
                    )

    return missing


class TestRequiresDecorator:
    def test_all_endpoints_have_requires(self) -> None:
        """Every @router.post / @router.get endpoint must have @requires.

        If you're adding a new endpoint, add @requires("edit") or
        @requires("read") depending on the permission level needed.

        Only endpoints in EXEMPT_ENDPOINTS are allowed to skip @requires
        (e.g. the login endpoint which must be accessible without auth).
        """
        missing = _get_endpoints_missing_requires()
        assert not missing, (
            "Endpoints missing @requires decorator:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\nAdd @requires('edit') or @requires('read') to each."
        )

    def test_endpoints_dir_exists(self) -> None:
        assert ENDPOINTS_DIR.is_dir(), (
            f"Endpoints dir not found: {ENDPOINTS_DIR}"
        )

    def test_finds_at_least_some_endpoints(self) -> None:
        """Sanity check that the AST parsing actually finds endpoints."""
        count = 0
        for filepath in ENDPOINTS_DIR.glob("*.py"):
            source = filepath.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    continue
                for decorator in node.decorator_list:
                    if (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "post"
                    ):
                        count += 1
        # We know there are many POST endpoints
        assert count > 30, f"Expected 30+ POST endpoints, found {count}"
