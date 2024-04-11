#!/bin/sh

echo "[fix: copyright]"
./scripts/pycopyright.sh
echo "[fix: ruff]"
ruff check marimo/ --fix
ruff check tests/ --fix
echo "[fix: black]"
black marimo/
black tests/
./scripts/pycheck.sh
