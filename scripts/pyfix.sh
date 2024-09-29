#!/bin/sh

echo "[fix: typos]"
cd marimo && hatch run typos -w && cd -
echo "[fix: copyright]"
./scripts/pycopyright.sh
echo "[fix: ruff]"
hatch run ruff check marimo/ --fix
hatch run ruff check tests/ --fix
hatch run ruff format marimo/
hatch run ruff format tests/
./scripts/pycheck.sh
