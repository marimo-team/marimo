#!/bin/bash
set -e

usage() {
    echo "Usage: $0 [--py VERSION] [--optional] [-- PYTEST_ARGS...]"
    echo ""
    echo "Options:"
    echo "  --py VERSION   Python version (e.g. 3.12). Default: 3.12"
    echo "  --optional     Use test-optional env (includes optional deps)"
    echo ""
    echo "Everything after -- is forwarded to pytest."
    echo "If no -- is used, all unrecognized args are forwarded to pytest."
    echo ""
    echo "Examples:"
    echo "  $0 tests/_runtime/test_threads.py"
    echo "  $0 --py 3.11 --optional tests/_runtime/test_threads.py -v"
    echo "  $0 --py 3.13 -- tests/ -k 'test_foo' -x"
    exit 1
}

PY_VERSION="3.12"
ENV="test"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --py)
            PY_VERSION="$2"
            shift 2
            ;;
        --optional)
            ENV="test-optional"
            shift
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

exec uvx hatch run +py="$PY_VERSION" "$ENV:test" "$@"
