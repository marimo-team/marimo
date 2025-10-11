#!/bin/sh

echo "[check: typos]"
hatch run typos -w
echo "[check: copyright]"
./scripts/pycopyright.sh
echo "[check: lint]"
hatch run ruff check --fix
echo "[check: format]"
hatch run ruff format
echo "[check: typecheck]"
hatch run typecheck:check
echo "[check: update-lock]"
hatch run pixi lock
