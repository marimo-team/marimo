#!/bin/sh

echo "[fix: copyright]"
./scripts/pycopyright.sh
echo "[fix: ruff]"
ruff check marimo/ --fix
ruff check tests/ --fix
ruff format marimo/
ruff format tests/
./scripts/pycheck.sh
