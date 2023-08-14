#!/bin/sh

echo "[fix: copyright]"
./scripts/pycopyright.sh
echo "[fix: ruff]"
ruff marimo/ --fix
echo "[fix: black]"
black marimo/
./scripts/pycheck.sh
