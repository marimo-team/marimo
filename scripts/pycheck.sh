#!/bin/bash

echo "[check: lint]"
ruff marimo/
echo "[check: typecheck]"
mypy marimo/
