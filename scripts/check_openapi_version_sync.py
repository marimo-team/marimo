#!/usr/bin/env python3
"""Ensure OpenAPI info.version matches project version."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = ROOT / "pyproject.toml"
OPENAPI_PATH = ROOT / "packages" / "openapi" / "api.yaml"


def get_project_version(pyproject_path: Path) -> str:
    in_project_section = False
    section_pattern = re.compile(r"^\s*\[([^\]]+)\]\s*$")
    version_pattern = re.compile(
        r"""^\s*version\s*=\s*["']([^"']+)["']\s*(?:#.*)?$"""
    )

    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        section_match = section_pattern.match(line)
        if section_match:
            in_project_section = section_match.group(1) == "project"
            continue

        if not in_project_section:
            continue

        version_match = version_pattern.match(line)
        if version_match:
            return version_match.group(1)

    raise ValueError(
        f"Could not find [project].version in {pyproject_path}."
    )


def get_openapi_info_version(openapi_path: Path) -> str:
    in_info_section = False
    info_indent = 0
    version_pattern = re.compile(r"^\s*version:\s*(.+?)\s*$")

    for line in openapi_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        indent = len(line) - len(line.lstrip(" "))

        if not in_info_section:
            if stripped == "info:" and indent == 0:
                in_info_section = True
                info_indent = indent
            continue

        if indent <= info_indent and not stripped.startswith("#"):
            break

        if indent > info_indent:
            version_match = version_pattern.match(line)
            if version_match:
                value = version_match.group(1).strip()
                if (
                    (value.startswith('"') and value.endswith('"'))
                    or (value.startswith("'") and value.endswith("'"))
                ) and len(value) >= 2:
                    value = value[1:-1]
                return value

    raise ValueError(
        f"Could not find info.version in {openapi_path}."
    )


def main() -> int:
    project_version = get_project_version(PYPROJECT_PATH)
    openapi_version = get_openapi_info_version(OPENAPI_PATH)

    if project_version == openapi_version:
        print(
            "OpenAPI version check passed: "
            f"pyproject={project_version}, openapi={openapi_version}"
        )
        return 0

    print("OpenAPI version mismatch detected:")
    print(f"  pyproject.toml [project].version: {project_version}")
    print(f"  packages/openapi/api.yaml info.version: {openapi_version}")
    print("Run `make fe-codegen` to regenerate packages/openapi/api.yaml.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
