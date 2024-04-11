#!/bin/sh

echo "[check: lint]"
ruff check marimo/
echo "[check: typecheck]"
mypy marimo/
