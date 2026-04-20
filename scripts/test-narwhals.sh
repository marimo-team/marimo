#!/bin/bash
set -e

# This script is used externally by the narwhals repo to run marimo tests
# that exercise narwhals. It is ok to test more than narwhals here, but we
# should not test less.
#
# Usage: scripts/test-narwhals.sh [--python VERSION]

PY_VERSION="3.12"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --python)
            PY_VERSION="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

exec uv run --python "$PY_VERSION" --group test-optional python -m pytest \
    tests/_data/ \
    tests/_plugins/ui/_impl/ \
    tests/_utils/test_narwhals_utils.py
