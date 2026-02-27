#!/bin/sh

echo "[check: typos]"
uv run typos -w
echo "[check: copyright]"
./scripts/pycopyright.sh
echo "[check: lint]"
uv run ruff check --fix
echo "[check: format]"
uv run ruff format
echo "[check: typecheck]"
uv run --group typecheck mypy marimo --exclude=marimo/_tutorials/
echo "[check: update-lock]"
uv run pixi lock
