#!/bin/sh

echo "[check: lint]"
ruff marimo/
echo "[check: typecheck]"
mypy marimo/
