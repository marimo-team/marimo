#!/bin/sh

echo "[fix: copyright]"
./scripts/pycopyright.sh
echo "[fix: ruff]"
ruff marimo/ --fix
ruff tests/ --fix
echo "[fix: black]"
black marimo/
black tests/
./scripts/pycheck.sh
