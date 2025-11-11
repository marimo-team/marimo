#!/bin/sh

echo "[check: typos]"
uvx hatch run typos -w
echo "[check: copyright]"
./scripts/pycopyright.sh
echo "[check: lint]"
uvx hatch run ruff check --fix
echo "[check: format]"
uvx hatch run ruff format
echo "[check: typecheck]"
uvx hatch run typecheck:check
echo "[check: update-lock]"
uvx hatch run pixi lock
