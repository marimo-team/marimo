# Copyright 2026 Marimo. All rights reserved.
"""Test that all POST endpoints have @requires decorator for auth."""

from __future__ import annotations

import ast
from pathlib import Path

# Endpoints that are intentionally exempt from @requires
EXEMPT_ENDPOINTS: set[tuple[str, str]] = {
    # Login endpoints must be accessible without authentication
    ("login.py", "/login"),
}

ENDPOINTS_DIR = Path(__file__).resolve().parents[4] / (
    "marimo/_server/api/endpoints"
)


def _get_post_endpoints_missing_requires() -> list[str]:
    """Parse all endpoint files and find POST routes missing @requires."""
    missing: list[str] = []

    for filepath in sorted(ENDPOINTS_DIR.glob("*.py")):
        filename = filepath.name
        if filename.startswith("_") or filename == "health.py":
            continue

        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            has_router_post = False
            post_path: str | None = None
            has_requires = False

            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func

                # Check for router.post(...)
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "post"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "router"
                    and decorator.args
                ):
                    has_router_post = True
                    post_path = ast.literal_eval(decorator.args[0])

                # Check for requires(...)
                if isinstance(func, ast.Name) and func.id == "requires":
                    has_requires = True

            if has_router_post and not has_requires:
                if (filename, post_path) not in EXEMPT_ENDPOINTS:
                    missing.append(
                        f"{filename}: POST {post_path} "
                        f"(function: {node.name}, line: {node.lineno})"
                    )

    return missing


class TestRequiresDecorator:
    def test_all_post_endpoints_have_requires(self) -> None:
        """Every @router.post endpoint must have a @requires decorator.

        If you're adding a new POST endpoint, add @requires("edit") or
        @requires("read") depending on the permission level needed.

        Only endpoints in EXEMPT_ENDPOINTS are allowed to skip @requires
        (e.g. the login endpoint which must be accessible without auth).
        """
        missing = _get_post_endpoints_missing_requires()
        assert not missing, (
            "POST endpoints missing @requires decorator:\n"
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
