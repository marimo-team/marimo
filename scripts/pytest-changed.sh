#!/bin/bash
set -e

usage() {
    echo "Usage: $0 [--python VERSION] [--group GROUP] [--from REF] [-- PYTEST_ARGS...]"
    echo ""
    echo "Run pytest on changed files across a matrix of Python versions."
    echo ""
    echo "Options:"
    echo "  --python VERSION  Run with a single Python version instead of the full matrix"
    echo "  --group GROUP    Dependency group: test or test-optional (default: test-optional)"
    echo "  --from REF       Git ref to diff against (default: main)"
    echo ""
    echo "Everything after -- is forwarded to pytest."
    echo "If no -- is used, all unrecognized args are forwarded to pytest."
    echo ""
    echo "Examples:"
    echo "  $0                                      # matrix of versions, test-optional, diff vs main"
    echo "  $0 --python 3.12                        # single version"
    echo "  $0 --group test                         # core deps only"
    echo "  $0 --from HEAD~3                        # diff against 3 commits ago"
    echo "  $0 -- -k 'test_foo' -x                  # forward flags to pytest"
    exit 1
}

PY_VERSIONS=("3.10" "3.11" "3.12" "3.13")
GROUP="test-optional"
CHANGED_FROM="main"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --python)
            PY_VERSIONS=("$2")
            shift 2
            ;;
        --group)
            GROUP="$2"
            shift 2
            ;;
        --from)
            CHANGED_FROM="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        --)
            shift
            break
            ;;
        *)
            break
            ;;
    esac
done

FAILED=()

for PY_VERSION in "${PY_VERSIONS[@]}"; do
    echo ""
    echo "============================================"
    echo "  Python $PY_VERSION / $GROUP"
    echo "============================================"
    echo ""

    if uv run --python "$PY_VERSION" --group "$GROUP" pytest tests/ \
        -v \
        -k "not test_cli" \
        --durations=10 \
        -p packages.pytest_changed \
        --changed-from="$CHANGED_FROM" \
        --include-unchanged=false \
        --picked=first \
        "$@"; then
        echo ""
        echo "  ✓ Python $PY_VERSION passed"
    else
        echo ""
        echo "  ✗ Python $PY_VERSION FAILED"
        FAILED+=("$PY_VERSION")
    fi
done

echo ""
echo "============================================"
echo "  Summary"
echo "============================================"

if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo ""
    echo "  FAILED: ${FAILED[*]}"
    echo ""
    exit 1
else
    echo ""
    echo "  All versions passed."
    echo ""
fi
