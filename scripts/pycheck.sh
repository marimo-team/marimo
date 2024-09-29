#!/bin/sh

echo "[check: lint]"
hatch run ruff check marimo/
echo "[check: typecheck]"
hatch run mypy marimo/
