#!/usr/bin/env uv run
"""
Python build tools generally only allow building
one project per Python project.

This modifies the pyproject.toml to build marimo-base,
a slimmed down marimo distribution with no static
artifacts.

Adapted from https://github.com/cvxpy/cvxpy/blob/297278e2a88db3c0084750052a16e60672074da3/.github/workflows/build.yml#L169C1-L180C1
"""
# /// script
# requires-python = ">=3.13"
# dependencies = ["tomlkit"]
#
# [tool.uv]
# exclude-newer = "2025-07-28T10:17:41.85442-04:00"
# ///

import pathlib
import tomlkit


root = pathlib.Path(__file__).parent.parent

force_exclude = [
    str(item.relative_to(root))
    for item in (root / "marimo/_static").iterdir()
    if item.name != "index.html"
]

with (root / "pyproject.toml").open(encoding="utf-8", mode="r") as f:
    data = tomlkit.load(f)


data["project"]["name"] = "marimo-base"
build_backend = data["tool"]["uv"]["build-backend"]

if "source-exclude" not in build_backend:
    build_backend["source-exclude"] = []
build_backend["source-exclude"].extend(force_exclude)

if "wheel-exclude" not in build_backend:
    build_backend["wheel-exclude"] = []
build_backend["wheel-exclude"].extend(force_exclude)

with (root / "pyproject.toml").open(encoding="utf-8", mode="w") as f:
    tomlkit.dump(data, f)

print("Successfully modified pyproject.toml for marimo-base build")
